"""Re-ingest enrichment JSONs into Neo4j without re-fetching from APIs.

Loads existing data/enrichment/{domain}.json files and writes them into
Neo4j using the ingestion pipeline. No network calls — pure local reads
+ Neo4j writes.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.reingest_from_json
    python -m scripts.reingest_from_json --init-schema
    python -m scripts.reingest_from_json --enrichment-dir data/enrichment --dataset data/dataset/attribution_dataset_v1.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from cti_agent.enrichment.models import DomainEnrichment
from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import get_settings
from cti_agent.graph.repository import GraphRepository
from cti_agent.graph.schema import init_schema
from cti_agent.ingestion.pipeline import ingest_batch
from cti_agent.models import DomainInput, load_domains_from_file

logging.basicConfig(
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-ingest enrichment JSONs into Neo4j")
    parser.add_argument("--enrichment-dir", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--dataset", type=Path, default=None,
                        help="JSONL dataset file for ground truth metadata (actor, family, source)")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--init-schema", action="store_true", help="Create Neo4j schema before ingesting")
    args = parser.parse_args()

    files = sorted(args.enrichment_dir.glob("*.json"))
    if not files:
        logger.error("No JSON files found in %s", args.enrichment_dir)
        return 1

    metadata_map: dict[str, DomainInput] = {}
    if args.dataset and args.dataset.exists():
        inputs = load_domains_from_file(args.dataset)
        metadata_map = {inp.domain: inp for inp in inputs}
        logger.info("Loaded %d ground truth entries from %s", len(metadata_map), args.dataset)

    dataset_domains = set(metadata_map.keys()) if metadata_map else None

    enrichments: list[DomainEnrichment] = []
    skipped = 0
    filtered_out = 0
    for i, path in enumerate(files, 1):
        if dataset_domains is not None and path.stem not in dataset_domains:
            filtered_out += 1
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            enrichments.append(DomainEnrichment.model_validate(data))
        except Exception as exc:
            logger.warning("Skipping %s: %s", path.name, exc)
            skipped += 1
        if i % 100 == 0:
            logger.info("[%d/%d] loaded", i, len(files))
    if filtered_out:
        logger.info("Filtered out %d enrichments not in dataset", filtered_out)

    logger.info("Loaded %d enrichments (%d skipped)", len(enrichments), skipped)

    settings = get_settings()

    if args.init_schema:
        with Neo4jClient(settings) as client:
            init_schema(client)
            logger.info("Schema initialized")

    start = time.monotonic()
    with Neo4jClient(settings) as client:
        repo = GraphRepository(client)
        report = ingest_batch(
            enrichments,
            repo,
            batch_size=args.batch_size,
            metadata_map=metadata_map if metadata_map else None,
        )
    duration = time.monotonic() - start

    logger.info("")
    logger.info("=== Re-ingestion Complete ===")
    logger.info("Enrichments ingested: %d", report.success)
    logger.info("Failures:             %d", len(report.failures))
    logger.info("Duration:             %.1fs", duration)
    if report.failures:
        for domain, error in report.failures[:10]:
            logger.warning("  FAILED: %s — %s", domain, error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
