"""End-to-end application entry: enrich a domain (Session B) and ingest the
result into Neo4j via the unified GraphRepository (Sessions C and A).

This module is the *application* entry point that wires the three sessions
together using a shared Neo4jSettings/Neo4jClient. It is not a new interface
layer; it only orchestrates the existing public functions.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from cti_agent.batch_report import BatchReport
from cti_agent.enrichment import enrich_batch, enrich_domain
from cti_agent.enrichment.models import DomainEnrichment
from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import Neo4jSettings, get_settings
from cti_agent.graph.repository import GraphRepository
from cti_agent.ingestion.pipeline import ingest_batch, ingest_domain_incremental
from cti_agent.ingestion.report import IngestReport
from cti_agent.models import DomainInput, load_domains_from_file

logger = logging.getLogger(__name__)

_UNSAFE_PATH_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_filename(domain: str) -> str:
    return _UNSAFE_PATH_RE.sub("_", domain)


def save_enrichment_json(
    enrichment: DomainEnrichment,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = _sanitize_filename(enrichment.domain) + ".json"
    path = output_dir / filename
    data = enrichment.model_dump_json_compatible()
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


async def run_enrich_and_ingest(
    domain: str,
    *,
    settings: Neo4jSettings | None = None,
    client: Neo4jClient | None = None,
) -> DomainEnrichment:
    """Enrich a single domain and write the result into Neo4j."""
    enrichment = await enrich_domain(domain)
    if client is not None:
        repo = GraphRepository(client)
        ingest_domain_incremental(enrichment, repo)
        return enrichment

    effective_settings = settings or get_settings()
    with Neo4jClient(effective_settings) as managed_client:
        repo = GraphRepository(managed_client)
        ingest_domain_incremental(enrichment, repo)
    return enrichment


async def run_enrich_and_ingest_batch(
    domains: list[str],
    *,
    concurrency: int | None = None,
    batch_size: int = 100,
    settings: Neo4jSettings | None = None,
    client: Neo4jClient | None = None,
) -> tuple[list[DomainEnrichment], IngestReport]:
    """Enrich many domains in parallel and ingest them in batched transactions."""
    enrichments = await enrich_batch(domains, concurrency=concurrency)
    if client is not None:
        repo = GraphRepository(client)
        report = ingest_batch(enrichments, repo, batch_size=batch_size)
        return enrichments, report

    effective_settings = settings or get_settings()
    with Neo4jClient(effective_settings) as managed_client:
        repo = GraphRepository(managed_client)
        report = ingest_batch(enrichments, repo, batch_size=batch_size)
    return enrichments, report


async def run_batch_pipeline(
    input_file: Path,
    *,
    output_dir: Path = Path("data/enrichment"),
    neo4j_settings: Neo4jSettings | None = None,
    concurrency: int | None = None,
    batch_size: int = 50,
) -> BatchReport:
    """Full M1 batch pipeline: file input -> enrich -> persist JSON -> ingest -> report."""
    start = time.monotonic()

    inputs = load_domains_from_file(input_file)
    if not inputs:
        logger.warning("No valid domains found in %s", input_file)
        return BatchReport()

    logger.info("Loaded %d domains from %s", len(inputs), input_file)
    domains = [inp.domain for inp in inputs]
    metadata_map = {inp.domain: inp for inp in inputs}

    enrichments = await enrich_batch(domains, concurrency=concurrency)

    for enrichment in enrichments:
        try:
            save_enrichment_json(enrichment, output_dir)
        except Exception as exc:
            logger.warning("Failed to save JSON for %s: %s", enrichment.domain, exc)

    effective_settings = neo4j_settings or get_settings()
    with Neo4jClient(effective_settings) as client:
        repo = GraphRepository(client)
        ingest_report = ingest_batch(
            enrichments,
            repo,
            batch_size=batch_size,
            metadata_map=metadata_map,
        )

    duration = time.monotonic() - start
    report = BatchReport.from_results(enrichments, ingest_report, duration)
    report.print_summary()
    return report
