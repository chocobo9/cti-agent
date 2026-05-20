"""LangGraph StateGraph wiring for the CTI attribution agent.

Task 4.10: Connects supervisor → infrastructure/intelligence → evidence_eval
with conditional iteration loop. Three-way routing from 4.9 determines
whether infrastructure runs first, intelligence first, or both parallel.

Design reference: Discussion Summary v4 §3.5 steps 1-6
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from cti_agent.agent.nodes.evidence_eval import evidence_evaluation_node
from cti_agent.agent.nodes.graph_probe import graph_probe_node
from cti_agent.agent.nodes.infrastructure import infrastructure_agent_node
from cti_agent.agent.nodes.intelligence import intelligence_agent_node
from cti_agent.agent.nodes.report import report_generation_node
from cti_agent.agent.schemas import AttributionState
from cti_agent.agent.supervisor import supervisor_query_analysis_node

_MAX_ITERATIONS = 2
_CONFIDENCE_THRESHOLD = 0.7


def _route_after_supervisor(state: dict) -> str:
    """Three-way routing based on query_type from supervisor analysis."""
    query_type = state.get("query_type", "mixed")
    if query_type == "structural":
        return "structural"
    if query_type == "semantic":
        return "semantic"
    return "mixed"


def _route_after_infrastructure(state: dict) -> str:
    """After infrastructure, always proceed to intelligence for evidence fusion."""
    return "intelligence"


def _should_continue(state: dict) -> str:
    """Decide whether to iterate or finish after evidence evaluation.

    Termination priority (checked in order):
      1. confidence ≥ threshold → finish
      2. iteration count ≥ max → finish
      3. no iteration templates selected → finish
      4. otherwise → iterate (Round 2)
    """
    if state.get("confidence", 0) >= _CONFIDENCE_THRESHOLD:
        return "finish"

    iteration = sum(
        1 for e in state.get("evidence_chain", [])
        if e.startswith("Evidence eval:")
    )
    if iteration >= _MAX_ITERATIONS:
        return "finish"

    routing = state.get("_routing_decision") or {}
    if not routing.get("templates"):
        return "finish"

    return "iterate"


def build_attribution_graph() -> StateGraph:
    """Construct the full attribution StateGraph with iteration loop.

    Graph topology:
        supervisor → conditional routing:
            structural  → infrastructure → intelligence → graph_probe → evidence_eval
            semantic    → intelligence → graph_probe → evidence_eval
            mixed       → infrastructure → intelligence → graph_probe → evidence_eval

        evidence_eval → conditional:
            iterate → infrastructure (loop back for more evidence)
            finish  → report → END
    """
    graph = StateGraph(AttributionState)

    graph.add_node("supervisor", supervisor_query_analysis_node)
    graph.add_node("infrastructure", infrastructure_agent_node)
    graph.add_node("intelligence", intelligence_agent_node)
    graph.add_node("evidence_eval", evidence_evaluation_node)
    graph.add_node("graph_probe", graph_probe_node)
    graph.add_node("report", report_generation_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "structural": "infrastructure",
            "semantic": "intelligence",
            "mixed": "infrastructure",
        },
    )

    graph.add_edge("infrastructure", "intelligence")
    graph.add_edge("intelligence", "graph_probe")
    graph.add_edge("graph_probe", "evidence_eval")

    graph.add_conditional_edges(
        "evidence_eval",
        _should_continue,
        {
            "iterate": "infrastructure",
            "finish": "report",
        },
    )
    graph.add_edge("report", END)

    return graph


def compile_attribution_graph(**kwargs: Any):
    """Build and compile the attribution graph with RemainingSteps config.

    Args:
        **kwargs: Passed to graph.compile(). Common options:
            - checkpointer: LangGraph checkpointer for persistence
            - interrupt_before/after: for human-in-the-loop

    Returns:
        Compiled LangGraph runnable.
    """
    graph = build_attribution_graph()
    return graph.compile(**kwargs)
