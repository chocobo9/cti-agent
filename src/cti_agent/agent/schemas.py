"""State and data schemas for the CTI attribution agent.

Task 4.1: Defines AttributionState (LangGraph shared state), QueryAnalysis
(LLM structured output), routing/evidence dataclasses, and Pydantic models
consumed by the Supervisor and tool functions.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict

from langgraph.managed import RemainingSteps
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LangGraph shared state
# ---------------------------------------------------------------------------

class AttributionState(TypedDict):
    # --- Input ---
    query: str
    domain: str | None

    # --- Supervisor decision ---
    query_type: str  # "structural" | "semantic" | "mixed"
    _routing_decision: dict | None

    # --- Infrastructure Agent output (graph queries) ---
    enrichment_data: dict | None
    graph_paths: Annotated[list[dict], operator.add]
    cluster_matches: list[dict]
    enrichment_suggested: bool

    # --- Intelligence Agent output (RAG retrieval) ---
    rag_chunks: Annotated[list[dict], operator.add]

    # --- Temporal confidence (95% DNS patterns decay within 90 days) ---
    temporal_confidence: float

    # --- Supervisor synthesis ---
    candidate_actors: list[dict]
    campaign_matches: list[dict]
    confidence: float
    evidence_chain: Annotated[list[str], operator.add]

    # --- Control ---
    needs_more_evidence: bool
    is_shared_infrastructure: bool
    remaining_steps: RemainingSteps

    # --- Report output ---
    attribution_report: dict | None

    # --- Error handling ---
    error_count: int
    last_error: str | None


# ---------------------------------------------------------------------------
# QueryAnalysis — LLM structured output for Supervisor call #1
# ---------------------------------------------------------------------------

class QueryAnalysis(BaseModel):
    """LLM extracts intent and entities; routing is done by deterministic code."""

    intent: Literal[
        "attribute_domain",
        "investigate_actor",
        "find_related_infrastructure",
        "general_cti_query",
    ] = Field(description="Core intent type of the query")

    target_domain: str | None = Field(
        default=None, description="Primary domain being investigated"
    )
    mentioned_ips: list[str] = Field(
        default_factory=list, description="IP addresses mentioned in the query"
    )
    mentioned_actors: list[str] = Field(
        default_factory=list, description="Threat actor / group names mentioned"
    )
    mentioned_malware: list[str] = Field(
        default_factory=list, description="Malware family names mentioned"
    )
    behavioral_description: str | None = Field(
        default=None,
        description="Attack technique / TTP description, only if user describes behavior",
    )
    reasoning: str = Field(
        description="Intent classification and entity extraction reasoning (for tracing)"
    )


# ---------------------------------------------------------------------------
# Routing dataclasses — deterministic code output, not LLM output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CypherInstruction:
    template_name: str
    params: dict[str, Any]
    priority: int = 0


@dataclass(frozen=True)
class RoutingDecision:
    query_type: str  # "structural" | "semantic" | "mixed"
    first_round_templates: list[CypherInstruction] = field(default_factory=list)
    rag_query_hints: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence evaluation — LLM structured output for Supervisor call #2
# ---------------------------------------------------------------------------

class ActorCandidate(BaseModel):
    actor_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list)
    source: str = Field(
        default="llm_inference",
        description="Evidence source: 'graph', 'rag', or 'llm_inference'",
    )


class EvidenceEvaluation(BaseModel):
    """Supervisor assesses whether collected evidence is sufficient."""

    confidence: float = Field(
        ge=0.0, le=1.0, description="Overall attribution confidence"
    )
    evidence_sufficiency: Literal["high", "medium", "low", "insufficient"] = Field(
        description="How sufficient is the evidence for attribution"
    )
    candidate_actors: list[ActorCandidate] = Field(default_factory=list)
    missing_evidence_types: list[str] = Field(
        default_factory=list,
        description="Enumerated types: infrastructure_pivot, ttp_corroboration, campaign_match, certificate_pivot, enrichment_needed",
    )
    evidence_gaps: list[str] = Field(
        default_factory=list,
        description="Free-text descriptions of what evidence is missing",
    )
    is_shared_infrastructure: bool = Field(
        default=False,
        description="True if MaaS / shared hosting detected",
    )
    needs_more_evidence: bool = Field(
        default=False,
        description="True if another query iteration is needed",
    )
    reasoning: str = Field(
        description="Evidence assessment reasoning (for tracing)"
    )
