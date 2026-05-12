"""Chainlit chat UI for the CTI Attribution Agent.

Launch::

    cd cti-agent
    chainlit run scripts/app_chainlit.py
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from cti_agent.agent.graph import compile_attribution_graph

        _graph = compile_attribution_graph()
    return _graph


@cl.on_chat_start
async def on_start():
    await cl.Message(content="CTI Attribution Agent ready. Send a query or use `/enrich <domain>` to collect OSINT data.").send()


@cl.on_message
async def on_message(message: cl.Message):
    user_text = message.content.strip()

    if user_text.lower().startswith("/enrich"):
        await _handle_enrich(user_text)
        return

    graph = _get_graph()
    msg = cl.Message(content="")
    await msg.send()

    try:
        state = await graph.ainvoke({"query": user_text})
    except Exception as exc:
        logger.exception("Attribution pipeline failed")
        msg.content = f"Pipeline error: {type(exc).__name__}: {exc}"
        await msg.update()
        return

    logger.info("state[\"query\"] = %r", state.get("query"))

    report_data = state.get("attribution_report")
    if not report_data:
        msg.content = "Pipeline returned no report."
        await msg.update()
        return

    from cti_agent.agent.nodes.report import AttributionReport, render_report_markdown

    report = AttributionReport(**report_data)
    md = render_report_markdown(report)
    msg.content = md
    await msg.update()

    evidence_chain = state.get("evidence_chain", [])
    if evidence_chain:
        evidence_text = "\n".join(evidence_chain)
        async with cl.Step(name="Evidence Chain", type="tool") as step:
            step.output = evidence_text


async def _handle_enrich(user_text: str):
    """Handle /enrich <domain> command — calls enrichment pipeline directly."""
    parts = user_text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await cl.Message(content="Usage: `/enrich <domain>` (e.g. `/enrich evil.com`)").send()
        return

    raw_domains = re.split(r"[,;\s]+", parts[1])
    cleaned = [_clean_domain(d) for d in raw_domains if d.strip()]
    cleaned = [d for d in cleaned if d and "." in d]

    if not cleaned:
        await cl.Message(content="No valid domains provided.").send()
        return

    msg = cl.Message(content=f"Enriching {len(cleaned)} domain(s): {', '.join(cleaned)} ...")
    await msg.send()

    try:
        from cti_agent.pipeline import run_enrich_and_ingest_batch, save_enrichment_json

        enrichments, ingest_report = await run_enrich_and_ingest_batch(cleaned)

        output_dir = Path(__file__).resolve().parent.parent / "data" / "enrichment"
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
        msg.content = "\n".join(lines)
        await msg.update()

    except Exception as exc:
        logger.exception("Enrichment pipeline failed")
        msg.content = f"Enrichment error: {exc}"
        await msg.update()
