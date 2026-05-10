"""Deterministic routing logic for the CTI attribution agent.

Tasks 4.9 + 4.10: Converts QueryAnalysis (LLM output) into RoutingDecision
(query_type + Cypher templates + RAG hints) using pure if/else rules.
Also provides iteration-loop functions: build_evidence_checklist and
select_iteration_templates for content-aware Round 2 template selection.
No LLM calls — fully testable and auditable.

Design reference: m4_module_h_design.md sections 5.1–5.4
"""

from __future__ import annotations

from typing import Any

from cti_agent.agent.schemas import CypherInstruction, QueryAnalysis, RoutingDecision

_TEMPLATE_TO_CHECKLIST: dict[str, str] = {
    "domain_infrastructure": "infrastructure_data",
    "domain_to_actor": "actor_attribution",
    "actor_to_domains": "actor_domains",
    "shared_infrastructure": "shared_infra_evidence",
    "certificate_pivot": "certificate_evidence",
    "reverse_ip_lookup": "reverse_ip",
    "similar_incidents": "similar_incidents",
    "active_campaigns": "campaign_evidence",
}

_CHECKLIST_KEYS = list(_TEMPLATE_TO_CHECKLIST.values()) + ["rag_corroboration"]

_SATISFIED_STATUSES = frozenset({"success", "empty"})


def determine_query_type(analysis: QueryAnalysis) -> str:
    """Classify query as structural / semantic / mixed based on extracted entities."""
    has_ioc = bool(analysis.target_domain or analysis.mentioned_ips)
    has_concrete_entity = has_ioc or bool(analysis.mentioned_actors)
    has_behavior = bool(analysis.behavioral_description)

    if analysis.intent == "general_cti_query":
        return "semantic"
    if has_concrete_entity and not has_behavior:
        return "structural"
    if has_behavior and not has_concrete_entity:
        return "semantic"
    return "mixed"


def select_templates(analysis: QueryAnalysis) -> list[CypherInstruction]:
    """Select first-round Cypher templates based on intent and extracted entities."""
    if analysis.intent == "attribute_domain":
        d = analysis.target_domain
        if d is None:
            return []
        return [
            CypherInstruction("domain_infrastructure", {"domain": d}, 0),
            CypherInstruction("domain_to_actor", {"domain": d}, 0),
            CypherInstruction("shared_infrastructure", {"domain": d}, 1),
        ]

    if analysis.intent == "investigate_actor":
        templates: list[CypherInstruction] = []
        for actor in analysis.mentioned_actors:
            templates.append(CypherInstruction("actor_to_domains", {"actor": actor}, 0))
            templates.append(CypherInstruction("active_campaigns", {"actor": actor}, 1))
        return templates

    if analysis.intent == "find_related_infrastructure":
        templates = []
        for ip in analysis.mentioned_ips:
            templates.append(CypherInstruction("reverse_ip_lookup", {"ip": ip}, 0))
        if analysis.target_domain:
            templates.append(
                CypherInstruction("domain_to_actor", {"domain": analysis.target_domain}, 1)
            )
        return templates

    # general_cti_query → no templates, pure RAG
    return []


def build_rag_hints(analysis: QueryAnalysis) -> list[str]:
    """Build RAG query strings from extracted entities and behavioral descriptions."""
    hints: list[str] = []
    if analysis.behavioral_description:
        hints.append(analysis.behavioral_description)
    if analysis.target_domain:
        hints.append(f"threat intelligence related to domain {analysis.target_domain}")
    for actor in analysis.mentioned_actors:
        hints.append(f"threat reports about {actor}")
    for malware in analysis.mentioned_malware:
        hints.append(f"analysis of {malware} malware family")
    return hints or ["general cyber threat intelligence"]


def build_routing_decision(analysis: QueryAnalysis) -> RoutingDecision:
    """Full routing pipeline: query_type + templates + RAG hints."""
    return RoutingDecision(
        query_type=determine_query_type(analysis),
        first_round_templates=select_templates(analysis),
        rag_query_hints=build_rag_hints(analysis),
    )


def select_followup_templates(
    analysis: QueryAnalysis, first_round_results: dict
) -> list[CypherInstruction]:
    """Select second-round templates based on first-round results.

    Rules:
      - T1 returned certificates → add T5 (certificate_pivot)
      - T2 returned cluster_tag_set → add T7 (similar_incidents)
      - T6 returned domains → add T2 for top 5 (domain_to_actor)
    """
    followup: list[CypherInstruction] = []

    infra = first_round_results.get("domain_infrastructure", {})
    if infra.get("certificates"):
        followup.append(
            CypherInstruction("certificate_pivot", {"domain": analysis.target_domain}, 0)
        )

    actor_result = first_round_results.get("domain_to_actor", {})
    if actor_result.get("cluster_tag_set"):
        followup.append(
            CypherInstruction(
                "similar_incidents",
                {"cluster_tag_set": actor_result["cluster_tag_set"]},
                0,
            )
        )

    reverse = first_round_results.get("reverse_ip_lookup", {})
    for domain_dict in reverse.get("domains", [])[:5]:
        domain_name = domain_dict.get("name") if isinstance(domain_dict, dict) else domain_dict
        if domain_name:
            followup.append(
                CypherInstruction("domain_to_actor", {"domain": domain_name}, 1)
            )

    return followup


# ---------------------------------------------------------------------------
# Task 4.10: Iteration loop — evidence checklist + iteration template selection
# ---------------------------------------------------------------------------


def build_evidence_checklist(
    graph_paths: list[dict[str, Any]],
    rag_chunks: list[dict[str, Any]],
    candidate_actors: list[dict[str, Any]],
) -> dict[str, bool]:
    """Build a boolean checklist of which evidence categories have been satisfied.

    A template item is True if any graph_path carries that template with
    status "success" or "empty" (empty = entity exists but no related data;
    retrying won't produce new information).

    RAG corroboration is True when any chunk content mentions a candidate
    actor name (case-insensitive substring match).
    """
    satisfied_templates: set[str] = set()
    for path in graph_paths:
        template = path.get("template", "")
        status = path.get("status", "")
        if status in _SATISFIED_STATUSES:
            checklist_key = _TEMPLATE_TO_CHECKLIST.get(template)
            if checklist_key:
                satisfied_templates.add(checklist_key)

    checklist: dict[str, bool] = {
        key: key in satisfied_templates for key in _TEMPLATE_TO_CHECKLIST.values()
    }

    actor_names = [
        a.get("actor_name", "").lower()
        for a in candidate_actors
        if a.get("actor_name")
    ]
    rag_corroborated = False
    if actor_names:
        for chunk in rag_chunks:
            content = (chunk.get("content") or "").lower()
            if any(name in content for name in actor_names):
                rag_corroborated = True
                break

    checklist["rag_corroboration"] = rag_corroborated
    return checklist


def select_iteration_templates(
    checklist: dict[str, bool],
    candidate_actors: list[dict[str, Any]],
    is_shared_infra: bool,
    intent: str,
    *,
    domain: str | None = None,
    ips: list[str] | None = None,
) -> tuple[list[CypherInstruction], list[str]]:
    """Select Round 2 Cypher templates and RAG hints from unsatisfied checklist items.

    Returns (templates, rag_hints). Both empty when checklist is fully
    satisfied or no templates can be parameterized.
    """
    templates: list[CypherInstruction] = []
    seen: set[str] = set()

    def _add(name: str, params: dict[str, Any]) -> None:
        key = f"{name}|{sorted(params.items())}"
        if key not in seen:
            seen.add(key)
            templates.append(CypherInstruction(name, params, 0))

    top_actor = (
        candidate_actors[0].get("actor_name")
        if candidate_actors
        else None
    )

    if not checklist.get("certificate_evidence") and domain:
        _add("certificate_pivot", {"domain": domain})

    if not checklist.get("reverse_ip") and ips:
        _add("reverse_ip_lookup", {"ip": ips[0]})

    if not checklist.get("actor_domains") and top_actor:
        _add("actor_to_domains", {"actor": top_actor})

    if not checklist.get("campaign_evidence") and top_actor:
        _add("active_campaigns", {"actor": top_actor})

    if is_shared_infra and ips:
        _add("reverse_ip_lookup", {"ip": ips[0]})

    hints: list[str] = []
    for actor in candidate_actors:
        name = actor.get("actor_name")
        if name:
            hints.append(f"threat intelligence about {name}")
    if is_shared_infra:
        hints.append("alternative threat actors with similar infrastructure")

    if not templates:
        return [], []

    return templates, hints
