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

    def to_frontend_source(self) -> str:
        """Normalize source value for frontend: llm_inference → llm."""
        return "llm" if self.source == "llm_inference" else self.source


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


# ---------------------------------------------------------------------------
# Frontend API response — shared contract between backend and frontend
# ---------------------------------------------------------------------------


class SourceEntry(BaseModel):
    type: Literal["graph", "rag", "llm"]
    detail: str


class GraphPathEntry(BaseModel):
    status: str
    template: str = ""
    summary: str = ""


class RagChunkEntry(BaseModel):
    chunk_id: str = ""
    source: str = ""
    rrf_score: float = 0.0
    snippet: str = ""


class FrontendActorCandidate(BaseModel):
    """ActorCandidate with frontend-normalized source field."""
    actor_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["graph", "rag", "llm"] = "llm"
    supporting_evidence: list[str] = Field(default_factory=list)

    @classmethod
    def from_backend(cls, actor: ActorCandidate) -> FrontendActorCandidate:
        return cls(
            actor_name=actor.actor_name,
            confidence=actor.confidence,
            source=actor.to_frontend_source(),  # type: ignore[arg-type]
            supporting_evidence=actor.supporting_evidence,
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FrontendActorCandidate:
        raw_source = d.get("source", "llm_inference")
        normalized = "llm" if raw_source == "llm_inference" else raw_source
        if normalized not in ("graph", "rag", "llm"):
            normalized = "llm"
        return cls(
            actor_name=d.get("actor_name", ""),
            confidence=min(max(d.get("confidence", 0.0), 0.0), 1.0),
            source=normalized,  # type: ignore[arg-type]
            supporting_evidence=d.get("supporting_evidence", []),
        )


class FrontendResponse(BaseModel):
    """API response contract — matches frontend TypeScript AttributionState."""

    query: str = ""
    domain: str = ""
    query_type: Literal["structural", "semantic", "mixed"] = "structural"

    attribution_result: Literal[
        "high_confidence", "medium_confidence", "low_confidence", "insufficient"
    ] = "insufficient"
    confidence: float = 0.0
    temporal_confidence: float = 0.0
    is_shared_infrastructure: bool = False
    needs_more_evidence: bool = False

    candidate_actors: list[FrontendActorCandidate] = Field(default_factory=list)
    enrichment: dict[str, Any] = Field(default_factory=dict)
    graph_paths: list[GraphPathEntry] = Field(default_factory=list)
    rag_chunks: list[RagChunkEntry] = Field(default_factory=list)
    evidence_chain: list[str] = Field(default_factory=list)
    narrative: str = ""
    sources: list[SourceEntry] = Field(default_factory=list)

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> FrontendResponse:
        """Transform LangGraph state dict into frontend-compatible response.

        No string parsing — builds typed fields from structured data only.
        """
        report: dict[str, Any] = state.get("attribution_report") or {}

        raw_candidates = state.get("candidate_actors", [])
        candidates = [FrontendActorCandidate.from_dict(c) for c in raw_candidates]

        raw_graph_paths = state.get("graph_paths", [])
        graph_paths = [
            GraphPathEntry(
                status=gp.get("status", "empty"),
                template=gp.get("template", ""),
                summary=gp.get("summary", ""),
            )
            for gp in raw_graph_paths
        ]

        raw_rag_chunks = state.get("rag_chunks", [])
        rag_chunks = [
            RagChunkEntry(
                chunk_id=rc.get("chunk_id", ""),
                source=rc.get("source", ""),
                rrf_score=rc.get("rrf_score", 0.0),
                snippet=rc.get("snippet", ""),
            )
            for rc in raw_rag_chunks
        ]

        sources: list[SourceEntry] = []
        for gp in raw_graph_paths:
            if gp.get("status") == "success":
                sources.append(SourceEntry(type="graph", detail=gp.get("template", "")))
        for chunk in raw_rag_chunks[:5]:
            sources.append(SourceEntry(type="rag", detail=f"{chunk.get('chunk_id', '')} ({chunk.get('source', '')})"))

        qt = state.get("query_type", "structural")
        if qt not in ("structural", "semantic", "mixed"):
            qt = "structural"

        ar = report.get("attribution_result", "insufficient")
        if ar not in ("high_confidence", "medium_confidence", "low_confidence", "insufficient"):
            ar = "insufficient"

        return cls(
            query=state.get("query", ""),
            domain=state.get("domain") or "",
            query_type=qt,  # type: ignore[arg-type]
            attribution_result=ar,  # type: ignore[arg-type]
            confidence=state.get("confidence", 0.0),
            temporal_confidence=state.get("temporal_confidence", 0.0),
            is_shared_infrastructure=state.get("is_shared_infrastructure", False),
            needs_more_evidence=state.get("needs_more_evidence", False),
            candidate_actors=candidates,
            enrichment=state.get("enrichment_data") or {},
            graph_paths=graph_paths,
            rag_chunks=rag_chunks,
            evidence_chain=state.get("evidence_chain", []),
            narrative=report.get("narrative_summary") or "",
            sources=sources,
        )
