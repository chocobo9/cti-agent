"""Intelligence Agent node — multi-query RAG retrieval with query rewriting.

Task 4.6: Rewrites user query into 2-3 diverse search queries via DeepSeek,
retrieves top-5 chunks per query, RRF-merges to top-10, writes rag_chunks
to state.

References:
    DMQR-RAG (arXiv:2411.13154, 2024) — diverse multi-query rewriting
    RAG-Fusion (arXiv:2402.03367, 2024) — multi-query + RRF fusion
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from cti_agent.agent.prompts import QUERY_REWRITING_SYSTEM_PROMPT, QUERY_REWRITING_USER_TEMPLATE
from cti_agent.agent.supervisor import _get_llm
from cti_agent.agent.tools.rag_retriever import retrieve_cti_chunks

logger = logging.getLogger(__name__)

_MAX_QUERIES = 3
_TOP_K_PER_QUERY = 5
_TOP_N_MERGED = 10
_RRF_K = 60


# ---------------------------------------------------------------------------
# Query rewriting (LLM free text -> split to queries)
# ---------------------------------------------------------------------------


def _build_graph_context(state: dict) -> str:
    evidence = state.get("evidence_chain", [])
    infra_lines = [e for e in evidence if e.startswith("T")]
    if not infra_lines:
        return ""
    summary = "\n- ".join(infra_lines)
    return f"Infrastructure findings from graph analysis:\n- {summary}"


def _build_user_message(state: dict) -> str:
    routing = state.get("_routing_decision") or {}
    analysis = routing.get("analysis", {})
    rag_hints = routing.get("rag_hints", [])

    return QUERY_REWRITING_USER_TEMPLATE.format(
        query=state.get("query", ""),
        domains=analysis.get("target_domain") or "none",
        actors=", ".join(analysis.get("mentioned_actors", [])) or "none",
        ips=", ".join(analysis.get("mentioned_ips", [])) or "none",
        behavior=analysis.get("behavioral_description") or "none",
        rag_hints=", ".join(rag_hints) if rag_hints else "none",
        graph_context=_build_graph_context(state),
    )


@retry(
    stop=stop_after_attempt(2),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def _call_rewrite_llm(llm: Any, user_message: str) -> str:
    response = llm.invoke([
        SystemMessage(content=QUERY_REWRITING_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])
    return response.content


def _parse_queries(raw_text: str) -> list[str]:
    lines = raw_text.strip().splitlines()
    queries: list[str] = []
    for line in lines:
        cleaned = line.strip().lstrip("0123456789.-) ")
        if len(cleaned) >= 10:
            queries.append(cleaned)
    return queries[:_MAX_QUERIES]


def _rewrite_queries(state: dict) -> list[str]:
    user_msg = _build_user_message(state)
    try:
        llm = _get_llm()
        raw = _call_rewrite_llm(llm, user_msg)
        queries = _parse_queries(raw)
        if queries:
            logger.info("Query rewriting produced %d queries", len(queries))
            return queries
        logger.warning("Query rewriting returned no valid queries, using fallback")
    except Exception:
        logger.exception("Query rewriting LLM call failed, using fallback")

    routing = state.get("_routing_decision") or {}
    return routing.get("rag_hints", [])[:_MAX_QUERIES]


# ---------------------------------------------------------------------------
# Retrieval (sync wrapper for async parallel)
# ---------------------------------------------------------------------------


def _retrieve_per_query(query: str) -> list[dict[str, Any]]:
    return retrieve_cti_chunks(query, top_k=_TOP_K_PER_QUERY)


# ---------------------------------------------------------------------------
# RRF merge (consistent with CTI-RAG: 1/(k + rank + 1), 0-based rank)
# ---------------------------------------------------------------------------


def _rrf_merge(
    results_lists: list[list[dict[str, Any]]],
    k: int = _RRF_K,
    top_n: int = _TOP_N_MERGED,
) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    best: dict[str, dict[str, Any]] = {}

    for results in results_lists:
        for rank, chunk in enumerate(results):
            chunk_id = chunk.get("chunk_id", chunk.get("content", "")[:80])
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
            if chunk_id not in best or chunk.get("score", 0) > best[chunk_id].get("score", 0):
                best[chunk_id] = chunk

    ranked_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    merged: list[dict[str, Any]] = []
    for rank, cid in enumerate(ranked_ids[:top_n]):
        entry = dict(best[cid])
        entry["rrf_score"] = round(scores[cid], 6)
        entry["rrf_rank"] = rank
        merged.append(entry)
    return merged


# ---------------------------------------------------------------------------
# Evidence summary
# ---------------------------------------------------------------------------


def _build_evidence_summary(chunks: list[dict[str, Any]], queries: list[str]) -> str:
    if not chunks:
        return "RAG: no relevant chunks found"
    sources = sorted({c.get("source", "?") for c in chunks})
    top_score = max(c.get("rrf_score", c.get("score", 0)) for c in chunks)
    return (
        f"RAG: {len(chunks)} chunks from [{', '.join(sources)}], "
        f"top_score={top_score:.4f}, "
        f"queries={queries}"
    )


# ---------------------------------------------------------------------------
# Main LangGraph node
# ---------------------------------------------------------------------------


async def intelligence_agent_node(state: dict) -> dict:
    """Execute multi-query RAG retrieval with LLM-based query rewriting."""
    routing = state.get("_routing_decision") or {}
    rag_hints = routing.get("rag_hints", [])

    if not rag_hints and not state.get("query"):
        return {
            "rag_chunks": [],
            "evidence_chain": ["Intelligence: no query or hints to search"],
        }

    queries = await asyncio.to_thread(_rewrite_queries, state)

    retrieval_tasks = [
        asyncio.to_thread(_retrieve_per_query, q)
        for q in queries
    ]
    results_lists = await asyncio.gather(*retrieval_tasks)

    merged = _rrf_merge(list(results_lists))

    if not merged and rag_hints:
        logger.info("Primary retrieval empty, falling back to rag_hints")
        fallback_tasks = [
            asyncio.to_thread(_retrieve_per_query, hint)
            for hint in rag_hints[:_MAX_QUERIES]
        ]
        fallback_results = await asyncio.gather(*fallback_tasks)
        merged = _rrf_merge(list(fallback_results))
        queries = rag_hints[:_MAX_QUERIES]

    evidence = _build_evidence_summary(merged, queries)

    return {
        "rag_chunks": merged,
        "evidence_chain": [evidence],
    }
