"""M4.14: General-purpose ReAct orchestrator agent.

Wraps M1-M4 modules as LangGraph tools for natural language control
of the full CTI attribution pipeline.  Used by the Streamlit UI
(scripts/app.py) and importable for programmatic access.

Usage::

    from cti_agent.agent.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent()
    result = agent.invoke({"messages": [("user", "Analyze hamadryas.online")]})
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Input cleaning utilities
# ---------------------------------------------------------------------------

_DEFANG_RE = re.compile(r"\[\.\]")
_URL_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)


def _clean_domain(raw: str) -> str:
    """Strip URL scheme/path and restore defanged notation."""
    d = raw.strip()
    d = _DEFANG_RE.sub(".", d)
    d = _URL_SCHEME_RE.sub("", d)
    d = d.split("/")[0].split("?")[0].split("#")[0]
    d = d.lower().strip(".")
    return d


# ---------------------------------------------------------------------------
# LLM singleton
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_orchestrator_llm():
    from langchain_deepseek import ChatDeepSeek

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")
    return ChatDeepSeek(model="deepseek-chat", api_key=api_key)


@lru_cache(maxsize=1)
def _get_attribution_graph():
    from cti_agent.agent.graph import compile_attribution_graph

    return compile_attribution_graph()


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are a Cyber Threat Intelligence (CTI) analyst assistant powering an \
agentic attribution system. You help users investigate suspicious domains, \
analyze threat actors, and explore threat intelligence data.

## Available tools

1. **attribute_domain** - Attribute a domain to a threat actor via the \
knowledge graph (Neo4j) and RAG retrieval (Qdrant). Use when the user \
mentions a specific domain.
2. **process_domains** - Collect OSINT enrichment data for domains and \
ingest into the graph database. Use when a domain is not yet in the database.
3. **search_cti** - Search CTI reports via hybrid RAG (dense + sparse + RRF \
fusion). Use for general threat intelligence questions.

## Key behaviors

- When a user mentions a domain (with or without explicit instructions), \
call **attribute_domain**.
- If attribute_domain returns **enrichment_suggested=true**, the domain is \
not yet in the database. Inform the user and ask if they want to run \
enrichment. Do NOT automatically call process_domains.
- For questions about threat actors, TTPs, or campaigns without a specific \
domain, call **search_cti**.
- When multiple domains are mentioned, process them appropriately.
- For topics outside cybersecurity, respond directly without using tools.
- Present results clearly: highlight attribution result, confidence, key \
evidence, and caveats.
- Respond in the same language the user uses (Chinese or English).

## Error handling constraints

- If a tool returns **[SYSTEM_ERROR]**, do NOT retry the same tool with the \
same input. Report the error to the user.
- If attribution tools return errors, report the error honestly. Never \
generate attribution conclusions from your own knowledge when tools have failed.
- For search_cti results, if all relevance scores are below 0.05, tell the \
user no relevant CTI reports were found instead of presenting low-relevance \
generic results.
"""

# ---------------------------------------------------------------------------
# Tool 1: Domain Attribution
# ---------------------------------------------------------------------------


@tool
def attribute_domain(domain: str) -> str:
    """Attribute a suspicious domain to a threat actor. Returns an attribution
    report with candidate actors, confidence scores, and evidence chain.
    If the domain is not in the database, the result will include
    enrichment_suggested=true."""
    from cti_agent.agent.nodes.report import AttributionReport, render_report_markdown

    cleaned = _clean_domain(domain)
    if not cleaned:
        return "Error: no valid domain provided after cleaning input."

    try:
        graph = _get_attribution_graph()
        state = asyncio.run(graph.ainvoke({"query": f"Who is behind {cleaned}?"}))
    except Exception as exc:
        logger.exception("Attribution failed for %s", cleaned)
        return f"[SYSTEM_ERROR] Attribution pipeline crashed for {cleaned}: {type(exc).__name__}: {exc}"

    report_data = state.get("attribution_report")
    if not report_data:
        return f"Attribution pipeline returned no report for {cleaned}."

    report = AttributionReport(**report_data)
    md = render_report_markdown(report)

    meta_parts = [f"confidence={report.confidence}"]
    meta_parts.append(f"iterations={report.iterations_performed}")
    if report.enrichment_suggested:
        meta_parts.append("enrichment_suggested=true")
    if report.is_shared_infrastructure:
        meta_parts.append("shared_infrastructure=true")

    return f"{md}\n\n---\nMetadata: {', '.join(meta_parts)}"


# ---------------------------------------------------------------------------
# Tool 2: Domain Processing (Enrichment + Ingestion)
# ---------------------------------------------------------------------------


@tool
def process_domains(domains: str) -> str:
    """Run enrichment pipeline on domains (comma-separated). Collects data from
    6 OSINT sources (crt.sh, RDAP, JARM, Favicon, OTX pDNS, GeoIP) and ingests
    results into Neo4j graph database. Use this when a domain is not yet in the
    database."""
    from cti_agent.pipeline import run_enrich_and_ingest_batch, save_enrichment_json

    raw_list = re.split(r"[,;\s]+", domains)
    cleaned = [_clean_domain(d) for d in raw_list if d.strip()]
    cleaned = [d for d in cleaned if d and "." in d]

    if not cleaned:
        return "Error: no valid domains provided."

    try:
        enrichments, ingest_report = asyncio.run(
            run_enrich_and_ingest_batch(cleaned)
        )
    except Exception as exc:
        logger.exception("Enrichment pipeline failed")
        return f"Error during enrichment: {exc}"

    output_dir = _PROJECT_ROOT / "data" / "enrichment"
    for enrichment in enrichments:
        try:
            save_enrichment_json(enrichment, output_dir)
        except Exception:
            logger.warning("Failed to save JSON for %s", enrichment.domain)

    lines = [f"Processed {len(enrichments)} domain(s):"]
    for e in enrichments:
        sources: list[str] = []
        if e.passive_dns:
            sources.append("pDNS")
        if e.certificates:
            sources.append("crt.sh")
        if any(g.asn_number for g in e.geoip):
            sources.append("GeoIP")
        if e.registrar:
            sources.append("RDAP")
        if e.favicon_hash:
            sources.append("Favicon")
        if e.jarm_hash:
            sources.append("JARM")
        lines.append(f"  - {e.domain}: {', '.join(sources) or 'no data collected'}")

    lines.append(
        f"\nNeo4j ingestion: {ingest_report.success} succeeded, "
        f"{len(ingest_report.failures)} failed, "
        f"{ingest_report.skipped} skipped"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: Clustering & Campaign Discovery
# ---------------------------------------------------------------------------


@tool
def analyze_clusters(profile: str = "coverage_weighted") -> str:
    """Run clustering and campaign discovery on all enriched domains in the
    database. Computes distance matrix, runs DBSCAN/HDBSCAN clustering, and
    discovers campaigns via Leiden community detection.
    Profile options: 'coverage_weighted' (default), 'uniform'."""
    scripts_dir = _PROJECT_ROOT / "scripts"
    python = sys.executable

    steps = [
        (
            "Computing distance matrix",
            [python, str(scripts_dir / "compute_distance_matrix.py"),
             "--profile-name", profile],
        ),
        (
            "Running clustering and writing to graph",
            [python, str(scripts_dir / "m3_write_graph.py")],
        ),
        (
            "Discovering campaigns",
            [python, str(scripts_dir / "m3_campaign_discovery.py")],
        ),
    ]

    results: list[str] = []
    for step_name, cmd in steps:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if proc.returncode != 0:
                err = (proc.stderr or "unknown error").strip()[-500:]
                return f"Error in '{step_name}':\n{err}"
            results.append(f"{step_name}: completed")
            if proc.stdout:
                tail = proc.stdout.strip().split("\n")[-3:]
                results.extend(f"  {line}" for line in tail)
        except subprocess.TimeoutExpired:
            return f"Timeout in '{step_name}' (exceeded 600s limit)."
        except Exception as exc:
            return f"Error in '{step_name}': {exc}"

    return "\n".join(results)


# ---------------------------------------------------------------------------
# Tool 4: CTI Report Search
# ---------------------------------------------------------------------------


@tool
def search_cti(query: str) -> str:
    """Search CTI threat intelligence reports using hybrid RAG (dense + sparse
    + RRF fusion). Returns relevant report excerpts with sources and relevance
    scores."""
    from cti_agent.agent.tools.rag_retriever import retrieve_cti_chunks

    if not query.strip():
        return "Error: empty search query."

    chunks = retrieve_cti_chunks(query.strip(), top_k=5)
    if not chunks:
        return "No relevant CTI reports found for this query."

    lines = [f"Found {len(chunks)} relevant CTI report excerpts:\n"]
    for i, chunk in enumerate(chunks, 1):
        content = chunk.get("content", "")[:300]
        source = chunk.get("source", "unknown")
        score = chunk.get("score", 0.0)
        lines.append(f"[{i}] (source: {source}, score: {score:.4f})")
        lines.append(content)
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def create_orchestrator_agent(**kwargs: Any):
    """Create and compile the ReAct orchestrator agent.

    Args:
        **kwargs: Passed to create_react_agent (e.g., checkpointer).

    Returns:
        Compiled LangGraph agent ready for .invoke() or .ainvoke().
    """
    llm = _get_orchestrator_llm()
    # analyze_clusters intentionally excluded — heavyweight batch operation
    # (459s on 735 domains), not suitable for LLM-driven per-query invocation
    tools = [attribute_domain, process_domains, search_cti]
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        **kwargs,
    )
