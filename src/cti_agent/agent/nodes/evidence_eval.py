"""Supervisor Evidence Evaluation node (LLM call #2).

Task 4.7 + 4.11: Evaluates collected graph + RAG evidence, produces
EvidenceEvaluation structured output. LLM directly provides confidence
score and categorical sufficiency. Temporal summary and MaaS indicators
are passed as context to the LLM.

Design reference: Discussion Summary v4 §3.5 steps 3-5
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from cti_agent.agent.routing import build_evidence_checklist, select_iteration_templates
from cti_agent.agent.schemas import EvidenceEvaluation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAAS_ASNS = frozenset({
    13335,   # Cloudflare
    16509,   # Amazon/AWS
    14618,   # Amazon
    15169,   # Google Cloud
    8075,    # Microsoft Azure
    20940,   # Akamai
    54113,   # Fastly
    13238,   # Yandex Cloud
    396982,  # Google Cloud
    16276,   # OVH
})

_MAX_ITERATIONS = 2

# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

EVIDENCE_EVALUATION_SYSTEM_PROMPT = """\
You are a CTI attribution analyst evaluating collected evidence.

Your task: assess whether the infrastructure graph evidence and threat intelligence report evidence are sufficient to attribute a domain/query to a specific threat actor.

## Output requirements:

### confidence (0.0-1.0):
- 0.9-1.0: Direct graph path (domain → campaign → actor) with corroborating RAG evidence
- 0.7-0.9: Strong infrastructure overlap (shared IPs/certs/clusters) pointing to single actor
- 0.5-0.7: Circumstantial evidence (ASN/registrar patterns, behavioral TTPs from reports)
- 0.3-0.5: Weak signals (common hosting, generic patterns)
- 0.0-0.3: Insufficient evidence or contradictory signals

### evidence_sufficiency (choose exactly one):
- "high": Direct graph path exists (domain → campaign → actor) AND corroborating RAG report evidence
- "medium": Strong infrastructure overlap pointing to single actor, OR RAG reports explicitly link the infrastructure to an actor
- "low": Only indirect signals (ASN/registrar patterns, generic TTP matches)
- "insufficient": No meaningful evidence, or evidence is contradictory

### candidate_actors:
- List ALL plausible actors with individual confidence (0.0-1.0) and supporting evidence strings
- If shared infrastructure detected: include multiple actors with lower individual confidence

### missing_evidence_types (use ONLY these exact values):
- "infrastructure_pivot": Need more infrastructure correlation (IP/cert/domain pivots)
- "ttp_corroboration": Need TTP/behavioral pattern corroboration from CTI reports
- "campaign_match": Need campaign matching verification
- "certificate_pivot": Need certificate data to support attribution
- "enrichment_needed": Domain not in graph, needs enrichment first

### evidence_gaps:
- Free-text descriptions of what specific evidence would strengthen the attribution

### is_shared_infrastructure:
- True if domain uses known CDN/cloud ASNs, shares IPs with many unrelated domains, or is flagged as shared hosting

### needs_more_evidence:
- True if evidence_sufficiency is "low" or "insufficient" AND actionable gaps exist
- False if evidence_sufficiency is "high" OR no actionable improvements possible

### reasoning:
- Step-by-step explanation of your assessment logic"""

EVIDENCE_EVALUATION_USER_TEMPLATE = """\
## Query
{query}

## Target domain
{domain}

## Graph evidence (infrastructure analysis summaries)
{graph_evidence}

## RAG evidence (CTI report chunks)
{rag_evidence}

## Temporal context
{temporal_description}

## MaaS indicators
{maas_indicators}

Evaluate the evidence and provide your attribution assessment:"""


# ---------------------------------------------------------------------------
# LLM interface
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_llm():
    from langchain_deepseek import ChatDeepSeek

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")
    return ChatDeepSeek(model="deepseek-chat", api_key=api_key)


@retry(
    stop=stop_after_attempt(2),
    retry=retry_if_exception_type((ValidationError, KeyError)),
)
def _call_evidence_eval(llm: Any, user_message: str) -> EvidenceEvaluation:
    structured_llm = llm.with_structured_output(EvidenceEvaluation)
    return structured_llm.invoke([
        SystemMessage(content=EVIDENCE_EVALUATION_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])


# ---------------------------------------------------------------------------
# Temporal summary (descriptive, for LLM context)
# ---------------------------------------------------------------------------


def _extract_age_days(data: dict) -> float | None:
    """Extract evidence age from a graph path data dict."""
    now = datetime.now(timezone.utc)
    for key in ("last_seen", "first_seen", "created_at"):
        ts = data.get(key)
        if ts and isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return (now - dt).days
            except (ValueError, TypeError):
                pass
    for ip_entry in data.get("ips", []):
        if isinstance(ip_entry, dict):
            for ts_key in ("last_seen", "first_seen"):
                ts = ip_entry.get(ts_key)
                if ts and isinstance(ts, str):
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        return (now - dt).days
                    except (ValueError, TypeError):
                        pass
    return None


def _lorentzian_decay(age_days: float, half_life: float, floor: float) -> float:
    """Lorentzian decay: 1 / (1 + age/half_life), clamped to floor."""
    return max(floor, 1.0 / (1.0 + age_days / half_life))


def compute_temporal_summary(graph_paths: list[dict]) -> dict[str, Any]:
    """Compute descriptive temporal summary for evidence chain and LLM context.

    Returns:
        dict with keys: median_age_days, min_date, max_date, description,
                        temporal_confidence
    """
    ages: list[float] = []
    dates: list[str] = []

    for path in graph_paths:
        if path.get("status") != "success":
            continue
        age = _extract_age_days(path.get("data", {}))
        if age is not None:
            ages.append(age)
        data = path.get("data", {})
        for key in ("first_seen", "last_seen"):
            ts = data.get(key)
            if ts and isinstance(ts, str):
                dates.append(ts[:10])

    logger.debug("temporal_summary: %d ages extracted from %d success paths, dates=%s", len(ages), sum(1 for p in graph_paths if p.get("status") == "success"), sorted(set(dates))[:5])

    if not ages:
        return {
            "median_age_days": None,
            "min_date": None,
            "max_date": None,
            "description": "No temporal data available in evidence",
            "temporal_confidence": 0.5,
        }

    median_age = sorted(ages)[len(ages) // 2]
    sorted_dates = sorted(set(dates)) if dates else []
    min_date = sorted_dates[0] if sorted_dates else None
    max_date = sorted_dates[-1] if sorted_dates else None

    if median_age < 30:
        desc = f"Very recent evidence (median {int(median_age)} days old)"
    elif median_age < 90:
        desc = f"Recent evidence (median {int(median_age)} days old)"
    elif median_age < 365:
        desc = f"Moderately aged evidence (median {int(median_age)} days old)"
    else:
        desc = f"Historical evidence (median {int(median_age)} days old, ~{median_age/365:.1f} years)"

    if min_date and max_date and min_date != max_date:
        desc += f", spanning {min_date} to {max_date}"

    temporal_confidence = _lorentzian_decay(median_age, 180, 0.1)

    return {
        "median_age_days": median_age,
        "min_date": min_date,
        "max_date": max_date,
        "description": desc,
        "temporal_confidence": round(temporal_confidence, 3),
    }


# ---------------------------------------------------------------------------
# MaaS / shared infrastructure detection
# ---------------------------------------------------------------------------


def detect_maas_indicators(graph_paths: list[dict]) -> dict[str, Any]:
    """Detect MaaS/shared infrastructure signals from graph evidence.

    Checks:
      1. ASN in known CDN/cloud list
      2. is_shared_hosting flag on ASN
      3. shared_infrastructure flag on domain (from dataset/T1 data)
      4. High shared domain count from T4
      5. Multiple unrelated actors from T2
    """
    indicators: list[str] = []
    shared_hosting_flag = False
    shared_domain_count = 0
    maas_asn_hits: list[int] = []
    domain_shared_infra_flag = False
    multi_actor_detected = False

    for path in graph_paths:
        if path.get("status") != "success":
            continue
        data = path.get("data", {})
        template = path.get("template", "")

        if template == "domain_infrastructure":
            for asn in data.get("asns", []):
                asn_num = asn.get("number")
                if asn_num and asn_num in _MAAS_ASNS:
                    maas_asn_hits.append(asn_num)
                    indicators.append(f"ASN {asn_num} ({asn.get('name', '?')}) is a known CDN/cloud provider")
                if asn.get("is_shared_hosting"):
                    shared_hosting_flag = True
                    indicators.append(f"ASN {asn_num} flagged as shared hosting")
            if data.get("shared_infrastructure"):
                domain_shared_infra_flag = True
                indicators.append("Domain flagged as shared_infrastructure in dataset")

        elif template == "shared_infrastructure":
            shared_domains = data.get("shared_domains", [])
            shared_domain_count = len(shared_domains)
            if shared_domain_count > 10:
                indicators.append(f"Domain shares IPs with {shared_domain_count} other domains (high sharing)")

        elif template == "domain_to_actor":
            actors = data.get("actors", [])
            if len(actors) > 1:
                multi_actor_detected = True
                actor_names = [a.get("name", "?") for a in actors]
                indicators.append(f"Multiple actors associated: {actor_names}")

    is_shared = (
        bool(maas_asn_hits)
        or shared_hosting_flag
        or domain_shared_infra_flag
        or shared_domain_count > 15
        or multi_actor_detected
    )

    return {
        "is_shared": is_shared,
        "indicators": indicators,
        "shared_hosting_flag": shared_hosting_flag,
        "domain_shared_infra_flag": domain_shared_infra_flag,
        "shared_domain_count": shared_domain_count,
        "maas_asn_hits": maas_asn_hits,
        "multi_actor_detected": multi_actor_detected,
    }


# ---------------------------------------------------------------------------
# Evidence formatting for LLM context
# ---------------------------------------------------------------------------


def _fallback_format_graph_evidence(graph_paths: list[dict]) -> str:
    """Fallback formatter when evidence_chain is empty."""
    lines: list[str] = []
    for path in graph_paths:
        status = path.get("status", "unknown")
        template = path.get("template", "?")
        if status == "success":
            data = path.get("data", {})
            parts = []
            for key, val in data.items():
                if isinstance(val, list):
                    if val and isinstance(val[0], dict) and "name" in val[0]:
                        names = [item["name"] for item in val[:5]]
                        parts.append(f"{key}: {names}")
                    else:
                        parts.append(f"{key}: {len(val)} items")
                elif val is not None:
                    parts.append(f"{key}: {val}")
            lines.append(f"[{template}] SUCCESS — {'; '.join(parts[:6])}")
        elif status == "no_match":
            suggestion = path.get("suggestion")
            lines.append(f"[{template}] NOT FOUND" + (f" (suggestions: {suggestion})" if suggestion else ""))
        elif status == "empty":
            lines.append(f"[{template}] EMPTY (entity exists but no related data)")
        elif status == "error":
            lines.append(f"[{template}] ERROR: {path.get('error', '?')}")
    return "\n".join(lines) if lines else "No graph evidence collected"


def _format_rag_evidence(rag_chunks: list[dict]) -> str:
    if not rag_chunks:
        return "No RAG evidence collected"
    lines: list[str] = []
    for i, chunk in enumerate(rag_chunks[:10]):
        source = chunk.get("source", "?")
        score = chunk.get("rrf_score", chunk.get("score", 0))
        content = chunk.get("content", "")[:300]
        lines.append(f"[{i+1}] source={source}, score={score:.4f}\n    {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallback evaluation (when LLM fails)
# ---------------------------------------------------------------------------


def _fallback_evaluation(
    graph_paths: list[dict],
    rag_chunks: list[dict],
    maas_info: dict[str, Any],
) -> EvidenceEvaluation:
    """Rule-based fallback when LLM call fails."""
    has_graph = any(p.get("status") == "success" for p in graph_paths)
    has_rag = len(rag_chunks) > 0
    has_enrichment_suggested = any(
        p.get("status") == "no_match" for p in graph_paths
    )

    if has_graph and has_rag:
        sufficiency = "medium"
        confidence = 0.6
    elif has_graph:
        sufficiency = "low"
        confidence = 0.5
    elif has_rag:
        sufficiency = "low"
        confidence = 0.4
    else:
        sufficiency = "insufficient"
        confidence = 0.1

    actors_from_graph: list[dict] = []
    for path in graph_paths:
        if path.get("status") == "success" and path.get("template") == "domain_to_actor":
            for actor in path.get("data", {}).get("actors", []):
                name = actor.get("name")
                if name:
                    actors_from_graph.append({
                        "actor_name": name,
                        "confidence": 0.6,
                        "supporting_evidence": ["graph path (fallback)"],
                    })

    missing: list[str] = []
    if not has_rag:
        missing.append("ttp_corroboration")
    if not has_graph:
        missing.append("infrastructure_pivot")
    if has_enrichment_suggested:
        missing.append("enrichment_needed")

    return EvidenceEvaluation(
        confidence=confidence,
        evidence_sufficiency=sufficiency,
        candidate_actors=actors_from_graph if actors_from_graph else [],
        missing_evidence_types=missing,
        evidence_gaps=["LLM evaluation unavailable — rule-based fallback used"],
        is_shared_infrastructure=maas_info["is_shared"],
        needs_more_evidence=sufficiency in ("low", "insufficient"),
        reasoning=f"Fallback: graph={'yes' if has_graph else 'no'}, rag={'yes' if has_rag else 'no'}, maas={maas_info['is_shared']}",
    )


# ---------------------------------------------------------------------------
# Main LangGraph node
# ---------------------------------------------------------------------------


async def evidence_evaluation_node(state: dict) -> dict:
    """LangGraph node: evaluate collected evidence (Supervisor LLM call #2).

    Reads: graph_paths, rag_chunks, query, domain, evidence_chain
    Writes: confidence, candidate_actors, campaign_matches, temporal_confidence,
            needs_more_evidence, is_shared_infrastructure, evidence_chain
    """
    graph_paths = state.get("graph_paths", [])
    rag_chunks = state.get("rag_chunks", [])
    query = state.get("query", "")
    domain = state.get("domain")

    # --- Iteration tracking ---
    evidence_chain = state.get("evidence_chain", [])
    prev_eval_count = sum(1 for e in evidence_chain if e.startswith("Evidence eval:"))
    iteration = prev_eval_count + 1

    # --- No-new-evidence detection (content-based: compare template+params signatures) ---
    prev_graph_count = 0
    for e in reversed(evidence_chain):
        if e.startswith("Evidence eval:") and "gp_count=" in e:
            try:
                prev_graph_count = int(e.split("gp_count=")[1].split(",")[0].split(")")[0])
            except (ValueError, IndexError):
                pass
            break
    new_paths = graph_paths[prev_graph_count:]
    prev_paths = graph_paths[:prev_graph_count]

    def _path_signature(p: dict) -> str:
        return f"{p.get('template', '')}|{sorted(p.get('params', {}).items())}|{p.get('status', '')}"

    prev_signatures = {_path_signature(p) for p in prev_paths}
    new_signatures = {_path_signature(p) for p in new_paths}
    has_new_evidence = bool(new_signatures - prev_signatures)

    # --- Temporal summary (descriptive, for LLM context) ---
    temporal_info = compute_temporal_summary(graph_paths)

    # --- MaaS detection ---
    maas_info = detect_maas_indicators(graph_paths)

    # --- Build LLM context ---
    infra_evidence_lines = [e for e in evidence_chain if e.startswith("T")]
    if infra_evidence_lines:
        graph_evidence_str = "\n".join(infra_evidence_lines)
    else:
        graph_evidence_str = _fallback_format_graph_evidence(graph_paths)

    rag_evidence_str = _format_rag_evidence(rag_chunks)
    maas_indicators_str = "\n".join(maas_info["indicators"]) if maas_info["indicators"] else "None detected"

    user_message = EVIDENCE_EVALUATION_USER_TEMPLATE.format(
        query=query,
        domain=domain or "N/A",
        graph_evidence=graph_evidence_str,
        rag_evidence=rag_evidence_str,
        temporal_description=temporal_info["description"],
        maas_indicators=maas_indicators_str,
    )

    # --- LLM call ---
    try:
        llm = _get_llm()
        evaluation = _call_evidence_eval(llm, user_message)
        if evaluation is None:
            raise ValueError("LLM returned None from structured output")
    except Exception:
        logger.exception("Evidence evaluation LLM call failed, using fallback")
        evaluation = _fallback_evaluation(graph_paths, rag_chunks, maas_info)

    # --- Final confidence: directly from LLM, no post-processing ---
    confidence = round(evaluation.confidence, 3)

    # --- needs_more_evidence (with hard constraints) ---
    forced_stop = "none"
    needs_more = evaluation.needs_more_evidence

    if not has_new_evidence and iteration > 1:
        needs_more = False
        forced_stop = "no_new"
    elif iteration >= _MAX_ITERATIONS:
        needs_more = False
        forced_stop = "max_iter"

    # --- Debug logging ---
    logger.info(
        "EvidenceEval [iter=%d/%d]: llm_confidence=%.3f, sufficiency=%s, "
        "needs_more=%s (llm=%s, forced_stop=%s), "
        "temporal_conf=%.3f, shared_infra=%s, new_evidence=%s, "
        "actors=[%s], graph_paths=%d, rag_chunks=%d",
        iteration, _MAX_ITERATIONS,
        confidence, evaluation.evidence_sufficiency,
        needs_more,
        evaluation.needs_more_evidence,
        forced_stop,
        temporal_info["temporal_confidence"],
        evaluation.is_shared_infrastructure or maas_info["is_shared"],
        has_new_evidence,
        ", ".join(a.actor_name for a in evaluation.candidate_actors),
        len(graph_paths),
        len(rag_chunks),
    )

    # --- Evidence summary for chain ---
    evidence_summary = (
        f"Evidence eval: confidence={confidence}, "
        f"sufficiency={evaluation.evidence_sufficiency}, "
        f"actors=[{', '.join(a.actor_name for a in evaluation.candidate_actors)}], "
        f"shared_infra={evaluation.is_shared_infrastructure or maas_info['is_shared']}, "
        f"needs_more={needs_more}, "
        f"iter={iteration}/{_MAX_ITERATIONS}, forced_stop={forced_stop}, "
        f"gp_count={len(graph_paths)}"
    )

    # --- Source attribution: tag each candidate actor with evidence source ---
    is_shared = evaluation.is_shared_infrastructure or maas_info["is_shared"]

    graph_actor_names: set[str] = set()
    for p in graph_paths:
        if p.get("status") == "success" and p.get("template") in ("domain_to_actor", "actor_to_domains", "active_campaigns"):
            for actor in p.get("data", {}).get("actors", []):
                name = actor.get("name") if isinstance(actor, dict) else None
                if name:
                    graph_actor_names.add(name)

    rag_mentioned_actors: set[str] = set()
    for chunk in rag_chunks:
        content_lower = (chunk.get("content") or "").lower()
        for candidate in evaluation.candidate_actors:
            if candidate.actor_name.lower() in content_lower:
                rag_mentioned_actors.add(candidate.actor_name)

    for candidate in evaluation.candidate_actors:
        if candidate.actor_name in graph_actor_names:
            candidate.source = "graph"
        elif candidate.actor_name in rag_mentioned_actors:
            candidate.source = "rag"

    actors_dicts = [a.model_dump() for a in evaluation.candidate_actors]

    # --- Iteration routing: compute Round 2 templates via pure functions ---

    routing_raw = state.get("_routing_decision") or {}
    intent = routing_raw.get("analysis", {}).get("intent") or routing_raw.get("intent", "general_cti_query")

    top_ips: list[str] = []
    for p in graph_paths:
        if p.get("template") == "domain_infrastructure" and p.get("status") == "success":
            for ip_entry in p.get("data", {}).get("ips", []):
                addr = ip_entry.get("address") if isinstance(ip_entry, dict) else None
                if addr:
                    top_ips.append(addr)
            top_ips = top_ips[:5]
            break

    checklist = build_evidence_checklist(graph_paths, rag_chunks, actors_dicts)
    iter_templates, iter_hints = select_iteration_templates(
        checklist, actors_dicts, is_shared, intent,
        domain=state.get("domain"), ips=top_ips,
    )

    iteration_routing: dict[str, Any] = {
        "templates": [
            {"template_name": t.template_name, "params": dict(t.params), "priority": t.priority}
            for t in iter_templates
        ],
        "rag_hints": iter_hints,
        "intent": intent,
    }

    return {
        "confidence": confidence,
        "candidate_actors": actors_dicts,
        "campaign_matches": [],
        "temporal_confidence": temporal_info["temporal_confidence"],
        "needs_more_evidence": needs_more,
        "is_shared_infrastructure": is_shared,
        "evidence_chain": [evidence_summary],
        "_routing_decision": iteration_routing,
    }
