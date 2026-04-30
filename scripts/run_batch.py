"""M1 Batch Pipeline — enrich domains from a JSONL file and ingest into Neo4j.

Prerequisites:
    1. Neo4j running (docker compose up -d)
    2. .env file with API keys (see .env.example)
    3. GeoLite2 databases extracted in data/ directory

Input file format (JSONL — one JSON object per line):
    {"domain": "evil.com", "source": "otx", "actor": "Comment Crew", "family": null, "shared_infrastructure": false}
    {"domain": "malware.net", "source": "threatfox", "actor": null, "family": "ClearFake", "shared_infrastructure": false}
    {"domain": "cs-beacon.io", "source": "threatfox", "actor": null, "family": "Cobalt Strike", "shared_infrastructure": true}

    Required fields: domain
    Optional fields: source (default "unknown"), actor, family, shared_infrastructure (default false)
    Lines starting with # are treated as comments. Blank lines are skipped.

Usage:
    # First run — initialize Neo4j schema + process domains:
    python -m scripts.run_batch data/raw/domains.jsonl --init-schema

    # Subsequent runs (schema already exists):
    python -m scripts.run_batch data/raw/domains.jsonl

    # Custom output directory and concurrency:
    python -m scripts.run_batch data/raw/domains.jsonl --output-dir data/enrichment --concurrency 5 --batch-size 25

    # Run from WSL (recommended on Windows):
    cd /mnt/d/proj/agent/cti-agent
    source /mnt/d/proj/agent/agent-venv/bin/activate
    python -m scripts.run_batch data/raw/domains.jsonl --init-schema

Options:
    input_file              Path to JSONL file with domain inputs
    --output-dir DIR        Directory for per-domain enrichment JSON (default: data/enrichment)
    --concurrency N         Max concurrent domain enrichments (default: 10)
    --batch-size N          Neo4j ingestion transaction batch size (default: 50)
    --init-schema           Create Neo4j constraints and indexes before running

Output:
    - Per-domain enrichment JSON saved to {output-dir}/{domain}.json
    - Domain nodes + relationships written to Neo4j (with ground truth metadata)
    - Console progress: [47/300] evil.com — crt.sh ✓, RDAP ✓, JARM ✗, pDNS ✓, favicon —, GeoIP ✓
    - Final summary: total/success/partial/failed counts + per-source success rates
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from cti_agent.graph.config import Neo4jSettings, get_settings
from cti_agent.graph.schema import init_schema
from cti_agent.pipeline import run_batch_pipeline


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M1 batch enrichment + ingestion pipeline")
    parser.add_argument("input_file", type=Path, help="JSONL file with domain inputs")
    parser.add_argument("--output-dir", type=Path, default=Path("data/enrichment"), help="Directory for enrichment JSON output")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrent domain enrichments")
    parser.add_argument("--batch-size", type=int, default=50, help="Neo4j ingestion batch size")
    parser.add_argument("--init-schema", action="store_true", help="Initialize Neo4j schema before running")
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.input_file.exists():
        logging.error("Input file not found: %s", args.input_file)
        return 1

    settings = get_settings()

    if args.init_schema:
        from cti_agent.graph.client import Neo4jClient

        with Neo4jClient(settings) as client:
            init_schema(client)

    report = await run_batch_pipeline(
        args.input_file,
        output_dir=args.output_dir,
        neo4j_settings=settings,
        concurrency=args.concurrency,
        batch_size=args.batch_size,
    )

    if report.completely_failed == report.total_domains and report.total_domains > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
