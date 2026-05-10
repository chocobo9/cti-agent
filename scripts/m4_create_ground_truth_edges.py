"""Create GROUND_TRUTH_ATTRIBUTION edges in Neo4j for M4 evaluation.

For each domain in the v2 dataset:
  - Actor group: Domain → GROUND_TRUTH_ATTRIBUTION → Actor node
  - Family group: Domain → GROUND_TRUTH_ATTRIBUTION → Actor node (entity_type: "malware_family")
  - Shared infra group: skipped (evaluation checks is_shared_infrastructure flag instead)

These edges are STRICTLY for evaluation — Agent Cypher templates never query them.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.m4_create_ground_truth_edges
    python -m scripts.m4_create_ground_truth_edges --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import get_settings

logging.basicConfig(format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

DATASET_PATH = Path("data/dataset/attribution_dataset_v2.jsonl")

MERGE_ACTOR_WITH_TYPE = """
MERGE (ac:Actor {name: $name})
ON CREATE SET ac.entity_type = $entity_type
"""

MERGE_GROUND_TRUTH = """
MATCH (d:Domain {name: $domain})
MATCH (ac:Actor {name: $actor_name})
MERGE (d)-[r:GROUND_TRUTH_ATTRIBUTION]->(ac)
ON CREATE SET r.source = 'ground_truth', r.dataset_group = $dataset_group
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create ground truth attribution edges for M4 evaluation")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    entries = []
    for line in args.dataset.read_text(encoding="utf-8").strip().split("\n"):
        entries.append(json.loads(line))
    logger.info("Dataset: %d entries", len(entries))

    actor_entries = []
    family_entries = []
    shared_count = 0

    for e in entries:
        group = e.get("group", "")
        if group == "actor_attribution" and e.get("actor"):
            actor_entries.append(e)
        elif group == "family_attribution" and e.get("family"):
            family_entries.append(e)
        elif group == "shared_infra" or e.get("shared_infrastructure"):
            shared_count += 1

    logger.info("Actor group: %d domains → ground truth edges", len(actor_entries))
    logger.info("Family group: %d domains → ground truth edges", len(family_entries))
    logger.info("Shared infra: %d domains → skipped (no edges)", shared_count)

    if args.dry_run:
        actors = set(e["actor"] for e in actor_entries)
        families = set(e["family"] for e in family_entries)
        logger.info("DRY RUN — would create:")
        logger.info("  Actor nodes: %d (%s...)", len(actors), sorted(actors)[:5])
        logger.info("  Family nodes: %d (%s)", len(families), sorted(families))
        logger.info("  GROUND_TRUTH_ATTRIBUTION edges: %d", len(actor_entries) + len(family_entries))
        return 0

    settings = get_settings()
    with Neo4jClient(settings) as client:
        actors_created: set[str] = set()

        for e in actor_entries:
            actor = e["actor"]
            if actor not in actors_created:
                client.execute_write(MERGE_ACTOR_WITH_TYPE, {"name": actor, "entity_type": "threat_actor"})
                actors_created.add(actor)

        for e in family_entries:
            family = e["family"]
            if family not in actors_created:
                client.execute_write(MERGE_ACTOR_WITH_TYPE, {"name": family, "entity_type": "malware_family"})
                actors_created.add(family)

        logger.info("Created/merged %d Actor nodes", len(actors_created))

        edge_count = 0
        for e in actor_entries:
            client.execute_write(MERGE_GROUND_TRUTH, {
                "domain": e["domain"], "actor_name": e["actor"], "dataset_group": "actor",
            })
            edge_count += 1

        for e in family_entries:
            client.execute_write(MERGE_GROUND_TRUTH, {
                "domain": e["domain"], "actor_name": e["family"], "dataset_group": "family",
            })
            edge_count += 1

    logger.info("")
    logger.info("=== Ground Truth Summary ===")
    logger.info("Actor nodes: %d", len(actors_created))
    logger.info("GROUND_TRUTH_ATTRIBUTION edges: %d", edge_count)
    logger.info("Verify: MATCH ()-[r:GROUND_TRUTH_ATTRIBUTION]->() RETURN count(r)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
