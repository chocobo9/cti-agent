"""Initialize and verify the Neo4j schema for the CTI Agent graph layer.

Purpose:
    Create the constraints and indexes required by the deterministic
    infrastructure graph before running ingestion or Milestone 1 smoke tests.
    The script can also run in verify-only mode to confirm an existing Neo4j
    database has all expected schema objects.

Usage:
    From WSL at the repo root, activate the shared virtualenv first:

        cd /mnt/d/proj/agent/cti-agent
        source ../agent-venv/bin/activate
        python -m scripts.init_neo4j_schema

    To only check existing schema without creating anything:

        python -m scripts.init_neo4j_schema --verify-only

    The script uses NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, and NEO4J_DATABASE
    from the environment or .env, falling back to the defaults in
    cti_agent.graph.config.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import get_settings
from cti_agent.graph.schema import init_schema, verify_schema


def missing_schema_items(result: dict[str, bool]) -> list[str]:
    return sorted(name for name, exists in result.items() if not exists)


def schema_exit_code(result: dict[str, bool]) -> int:
    return 0 if all(result.values()) else 1


def parse_args() -> Namespace:
    parser = ArgumentParser(description="Initialize and verify the CTI Agent Neo4j schema.")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip schema creation and only verify existing constraints/indexes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    with Neo4jClient(settings) as client:
        client.verify_connectivity()
        if not args.verify_only:
            init_schema(client)
        result = verify_schema(client)

    missing = missing_schema_items(result)
    if missing:
        print("Schema verification failed. Missing items:")
        for name in missing:
            print(f"- {name}")
    else:
        print("Schema verification passed. All constraints and indexes are present.")
    return schema_exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
