"""End-to-end application entry: enrich a domain (Session B) and ingest the
result into Neo4j via the unified GraphRepository (Sessions C and A).

This module is the *application* entry point that wires the three sessions
together using a shared Neo4jSettings/Neo4jClient. It is not a new interface
layer; it only orchestrates the existing public functions.
"""

from __future__ import annotations

from cti_agent.enrichment import enrich_batch, enrich_domain
from cti_agent.enrichment.models import DomainEnrichment
from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import Neo4jSettings, get_settings
from cti_agent.graph.repository import GraphRepository
from cti_agent.ingestion.pipeline import ingest_batch, ingest_domain_incremental
from cti_agent.ingestion.report import IngestReport


async def run_enrich_and_ingest(
    domain: str,
    *,
    settings: Neo4jSettings | None = None,
    client: Neo4jClient | None = None,
) -> DomainEnrichment:
    """Enrich a single domain and write the result into Neo4j.

    Pass `settings` to override the cached Neo4j configuration, or `client` to
    reuse an existing driver (caller-managed lifecycle). Returns the raw
    enrichment so callers can inspect features and partial errors.
    """
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
    """Enrich many domains in parallel and ingest them in batched transactions.

    Returns the enrichments alongside an IngestReport so callers can correlate
    success/failure counts with B-side `errors` per domain.
    """
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
