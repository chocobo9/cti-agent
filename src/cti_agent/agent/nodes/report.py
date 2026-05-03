"""Attribution report generation node (Supervisor output stage).

Task 4.8: Assembles accumulated evidence into a structured AttributionReport.
Deterministic assembly by default; optional LLM narrative summary when
REPORT_NARRATIVE=1 environment variable is set.

Design reference: Discussion Summary v4 §3.5 step 6
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AttributionReport(BaseModel):
    """Structured attribution report — the final system output."""

    query: str
    domain: str | None = None
    query_type: str = "unknown"

    attribution_result: str  # high_confidence | medium_confidence | low_confidence | insufficient
    primary_actor: str | None = None
    candidate_actors: list[dict] = Field(default_factory=list)
    confidence: float = 0.0
    temporal_confidence: float = 0.5

    is_shared_infrastructure: bool = False
    shared_infra_note: str | None = None

    campaign_associations: list[dict] = Field(default_factory=list)

    infrastructure_evidence: list[str] = Field(default_factory=list)
    intelligence_evidence: list[str] = Field(default_factory=list)
    evaluation_summaries: list[str] = Field(default_factory=list)

    iterations_performed: int = 1
    enrichment_suggested: bool = False
    timestamp: str = ""

    narrative_summary: str | None = None


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def classify_attribution_result(confidence: float) -> str:
    if confidence >= 0.7:
        return "high_confidence"
    if confidence >= 0.5:
        return "medium_confidence"
    if confidence >= 0.3:
        return "low_confidence"
    return "insufficient"


def partition_evidence_chain(
    chain: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Split evidence_chain into (infrastructure, intelligence, evaluation)."""
    infra: list[str] = []
    intel: list[str] = []
    evals: list[str] = []
    for entry in chain:
        if entry.startswith("Evidence eval:"):
            evals.append(entry)
        elif entry.startswith("RAG:"):
            intel.append(entry)
        elif entry.startswith("Query analyzed:"):
            pass
        else:
            infra.append(entry)
    return infra, intel, evals


def extract_campaigns(graph_paths: list[dict]) -> list[dict]:
    campaigns: list[dict] = []
    seen: set[str] = set()
    for path in graph_paths:
        if path.get("template") == "active_campaigns" and path.get("status") == "success":
            for c in path.get("data", {}).get("campaigns", []):
                if isinstance(c, dict):
                    cid = c.get("name") or c.get("campaign_id", "")
                    if cid and cid not in seen:
                        seen.add(cid)
                        campaigns.append(c)
    return campaigns


def build_shared_infra_note(
    graph_paths: list[dict], is_shared: bool
) -> str | None:
    if not is_shared:
        return None
    indicators: list[str] = []
    for path in graph_paths:
        if path.get("status") != "success":
            continue
        data = path.get("data", {})
        template = path.get("template", "")
        if template == "domain_infrastructure":
            for asn in data.get("asns", []):
                if asn.get("is_shared_hosting"):
                    indicators.append(
                        f"ASN {asn.get('number')} ({asn.get('name', '?')}) flagged as shared hosting"
                    )
        elif template == "shared_infrastructure":
            n = len(data.get("shared_domains", []))
            if n > 0:
                indicators.append(f"Shares IPs with {n} other domains")
    return "; ".join(indicators) if indicators else "Shared infrastructure detected"


# ---------------------------------------------------------------------------
# Report assembly (pure function)
# ---------------------------------------------------------------------------


def assemble_report(state: dict) -> AttributionReport:
    """Build an AttributionReport from the final LangGraph state."""
    confidence = state.get("confidence", 0.0)
    candidates = state.get("candidate_actors", [])
    evidence_chain = state.get("evidence_chain", [])
    graph_paths = state.get("graph_paths", [])
    is_shared = state.get("is_shared_infrastructure", False)

    infra_ev, intel_ev, eval_summaries = partition_evidence_chain(evidence_chain)
    iterations = sum(1 for e in evidence_chain if e.startswith("Evidence eval:"))

    return AttributionReport(
        query=state.get("query", ""),
        domain=state.get("domain"),
        query_type=state.get("query_type", "unknown"),
        attribution_result=classify_attribution_result(confidence),
        primary_actor=candidates[0].get("actor_name") if candidates else None,
        candidate_actors=candidates,
        confidence=round(confidence, 3),
        temporal_confidence=round(state.get("temporal_confidence", 0.5), 3),
        is_shared_infrastructure=is_shared,
        shared_infra_note=build_shared_infra_note(graph_paths, is_shared),
        campaign_associations=extract_campaigns(graph_paths),
        infrastructure_evidence=infra_ev,
        intelligence_evidence=intel_ev,
        evaluation_summaries=eval_summaries,
        iterations_performed=max(iterations, 1),
        enrichment_suggested=state.get("enrichment_suggested", False),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_report_markdown(report: AttributionReport) -> str:
    """Render an AttributionReport as human-readable Markdown."""
    lines: list[str] = []

    target = report.domain or report.query[:60]
    lines.append(f"# Attribution Report: {target}")
    lines.append("")

    badge = {
        "high_confidence": "HIGH CONFIDENCE",
        "medium_confidence": "MEDIUM CONFIDENCE",
        "low_confidence": "LOW CONFIDENCE",
        "insufficient": "INSUFFICIENT EVIDENCE",
    }.get(report.attribution_result, report.attribution_result.upper())
    lines.append(f"**Result**: {badge} (confidence: {report.confidence:.2f})")
    lines.append("")

    if report.primary_actor:
        lines.append("## Primary Attribution")
        for actor in report.candidate_actors:
            name = actor.get("actor_name", "?")
            conf = actor.get("confidence", 0)
            marker = " **(primary)**" if name == report.primary_actor else ""
            lines.append(f"- **{name}**{marker}: confidence {conf:.2f}")
            for ev in actor.get("supporting_evidence", [])[:3]:
                lines.append(f"  - {ev}")
        lines.append("")
    else:
        lines.append("## Attribution")
        lines.append("No candidate actors identified.")
        lines.append("")

    if report.is_shared_infrastructure:
        lines.append("## Shared Infrastructure Warning")
        lines.append(
            f"This domain uses shared/cloud infrastructure. {report.shared_infra_note or ''}"
        )
        lines.append("")

    if report.campaign_associations:
        lines.append("## Campaign Associations")
        for c in report.campaign_associations:
            name = c.get("name") or c.get("campaign_id", "?")
            lines.append(f"- {name}")
        lines.append("")

    lines.append("## Evidence Summary")
    if report.infrastructure_evidence:
        lines.append("### Infrastructure Analysis")
        for ev in report.infrastructure_evidence:
            lines.append(f"- {ev}")
        lines.append("")
    if report.intelligence_evidence:
        lines.append("### Intelligence Analysis")
        for ev in report.intelligence_evidence:
            lines.append(f"- {ev}")
        lines.append("")

    lines.append("## Metadata")
    lines.append(f"- Query type: {report.query_type}")
    lines.append(f"- Iterations: {report.iterations_performed}")
    lines.append(f"- Temporal confidence: {report.temporal_confidence:.3f}")
    lines.append(f"- Enrichment suggested: {'Yes' if report.enrichment_suggested else 'No'}")
    lines.append(f"- Timestamp: {report.timestamp}")

    if report.narrative_summary:
        lines.append("")
        lines.append("## Analysis Narrative")
        lines.append(report.narrative_summary)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Optional LLM narrative
# ---------------------------------------------------------------------------


def _generate_narrative(state: dict, report: AttributionReport) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    from cti_agent.agent.nodes.evidence_eval import _get_llm

    evidence_text = "\n".join(report.infrastructure_evidence[:10])
    intel_text = "\n".join(report.intelligence_evidence[:5])
    actors_text = ", ".join(
        f"{a.get('actor_name', '?')} ({a.get('confidence', 0):.2f})"
        for a in report.candidate_actors
    )

    prompt = (
        f"Domain: {report.domain or 'N/A'}\n"
        f"Confidence: {report.confidence:.2f}\n"
        f"Candidates: {actors_text or 'none'}\n"
        f"Shared infra: {report.is_shared_infrastructure}\n"
        f"Infrastructure:\n{evidence_text}\n"
        f"Intelligence:\n{intel_text}\n\n"
        "Write a 2-3 sentence analyst summary of the attribution findings."
    )

    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content="You are a CTI analyst writing a brief attribution summary."),
        HumanMessage(content=prompt),
    ])
    return response.content.strip()


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


async def report_generation_node(state: dict) -> dict:
    """LangGraph node: assemble structured attribution report.

    Reads: all accumulated state fields after evidence evaluation.
    Writes: attribution_report (dict)

    Set REPORT_NARRATIVE=1 to enable optional LLM narrative (1 DeepSeek call).
    """
    report = assemble_report(state)

    if os.environ.get("REPORT_NARRATIVE") == "1":
        try:
            report.narrative_summary = _generate_narrative(state, report)
        except Exception:
            logger.exception("Narrative generation failed, skipping")

    return {"attribution_report": report.model_dump()}
