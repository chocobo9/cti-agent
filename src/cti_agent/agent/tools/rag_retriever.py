"""CTI-RAG retrieval adapter for the attribution agent.

Task 4.3: Thin wrapper around rag_cti.query() that exposes retrieval-only
access (dense + sparse + RRF fusion).  Generation stays with the Supervisor.

Prerequisite: ``pip install -e D:\\proj\\CTI-RAG\\rag_cti`` into agent-venv.

rag_cti public API (from rag_cti/__init__.py):
    query(text: str, k: int = 10) -> QueryResult

QueryResult (frozen Pydantic):
    query: str
    results: list[RetrievalResult]   # .document: Chunk, .score, .rank, .retriever_source
    total_retrieved: int
    retrieval_ms: float

Chunk (frozen Pydantic):
    id, parent_doc_id, source, content, chunk_index, metadata, retrieved_at, embedding_model
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

_MAX_CONTENT_LENGTH = 500

try:
    from rag_cti import query as rag_query
except ImportError:
    rag_query = None  # type: ignore[assignment]
    logger.warning(
        "rag_cti not installed — run: pip install -e D:\\proj\\CTI-RAG\\rag_cti"
    )


def retrieve_cti_chunks(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Retrieve CTI report chunks via the existing hybrid RAG pipeline.

    Uses rag_cti.query() which runs: IOC-aware tokenization -> dense (bge-m3)
    + sparse (BM25) parallel search -> RRF fusion.

    Returns a list of dicts with keys: content, source, score, metadata.
    Returns empty list on any error (Qdrant down, import failure, etc.).
    """
    if rag_query is None:
        return []

    try:
        result = rag_query(query, k=top_k)
    except Exception:
        logger.exception("rag_cti.query() failed for query: %s", query[:100])
        return []

    chunks: list[dict[str, Any]] = []
    for r in result.results:
        doc = r.document
        chunks.append({
            "chunk_id": doc.id,
            "content": doc.content[:_MAX_CONTENT_LENGTH],
            "source": doc.source,
            "score": r.score,
            "metadata": doc.metadata,
        })
    return chunks
