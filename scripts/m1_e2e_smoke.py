"""Milestone 1 end-to-end smoke test.

Purpose:
    Verify the foundation pipeline with real domain input:
    enrichment -> Neo4j ingestion -> Cypher graph evidence check.
    This script is meant for local/operator validation, not as a normal unit
    test, because it can call external enrichment services and requires a
    reachable Neo4j instance.

Usage:
    From WSL at the repo root, activate the shared virtualenv first:

        cd /mnt/d/proj/agent/cti-agent
        source ../agent-venv/bin/activate
        python -m scripts.m1_e2e_smoke --init-schema --concurrency 1 example.com

    Run one or more domains after Neo4j is available on NEO4J_URI
    (default: bolt://localhost:7687). The script exits non-zero if ingestion
    fails or if any domain has no graph evidence such as IP, ASN, certificate,
    JARM, or favicon data.
"""

from __future__ import annotations

import asyncio
from argparse import ArgumentParser, Namespace
from typing import Any

from cti_agent.enrichment.models import DomainEnrichment
from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import get_settings
from cti_agent.graph.queries import count_nodes_by_label, get_full_attribution_path
from cti_agent.graph.schema import init_schema
from cti_agent.ingestion.report import IngestReport
from cti_agent.pipeline import run_enrich_and_ingest_batch

INFRASTRUCTURE_KEYS = (
    "ips",
    "asns",
    "certificates",
    "jarm_fingerprints",
    "favicon_hashes",
)


def domain_has_infrastructure(result: dict[str, Any]) -> bool:
    if not result.get("domain"):
        return False
    return any(bool(result.get(key)) for key in INFRASTRUCTURE_KEYS)


def summarize_enrichment_errors(enrichments: list[DomainEnrichment]) -> dict[str, dict[str, str]]:
    return {
        enrichment.domain: dict(enrichment.errors)
        for enrichment in enrichments
        if enrichment.errors
    }


def smoke_exit_code(report: IngestReport, graph_checks: dict[str, bool]) -> int:
    if report.failures:
        return 1
    if not graph_checks:
        return 1
    return 0 if all(graph_checks.values()) else 1


def parse_args() -> Namespace:
    parser = ArgumentParser(description="Run the Milestone 1 enrichment -> Neo4j smoke test.")
    parser.add_argument("domains", nargs="+", help="Domains to enrich, ingest, and verify.")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Maximum concurrent enrichment tasks.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for Neo4j ingestion.",
    )
    parser.add_argument(
        "--init-schema",
        action="store_true",
        help="Initialize Neo4j constraints and indexes before running the smoke test.",
    )
    return parser.parse_args()


async def run_smoke(args: Namespace) -> int:
    settings = get_settings()
    with Neo4jClient(settings) as client:
        client.verify_connectivity()
        if args.init_schema:
            init_schema(client)

        enrichments, report = await run_enrich_and_ingest_batch(
            list(args.domains),
            concurrency=args.concurrency,
            batch_size=args.batch_size,
            client=client,
        )

        graph_checks: dict[str, bool] = {}
        for domain in args.domains:
            path = get_full_attribution_path(client, domain)
            graph_checks[domain] = domain_has_infrastructure(path)

        node_counts = count_nodes_by_label(client)

    print("M1 smoke summary")
    print(f"- domains: {', '.join(args.domains)}")
    print(f"- ingest_success: {report.success}")
    print(f"- ingest_failures: {len(report.failures)}")
    print(f"- graph_checks: {graph_checks}")
    print(f"- node_counts: {node_counts}")

    partial_errors = summarize_enrichment_errors(enrichments)
    if partial_errors:
        print("- partial_enrichment_errors:")
        for domain, errors in partial_errors.items():
            print(f"  - {domain}: {errors}")

    if report.failures:
        print("- ingest_failures_detail:")
        for domain, error in report.failures:
            print(f"  - {domain}: {error}")

    return smoke_exit_code(report, graph_checks)


def main() -> int:
    return asyncio.run(run_smoke(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
