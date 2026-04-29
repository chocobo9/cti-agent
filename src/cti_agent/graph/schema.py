from __future__ import annotations

import logging
from typing import Final

from cti_agent.graph.client import Neo4jClient

logger = logging.getLogger(__name__)

UNIQUENESS_CONSTRAINTS: Final[list[str]] = [
    "CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT ip_address IF NOT EXISTS FOR (ip:IP) REQUIRE ip.address IS UNIQUE",
    "CREATE CONSTRAINT asn_number IF NOT EXISTS FOR (a:ASN) REQUIRE a.number IS UNIQUE",
    "CREATE CONSTRAINT cert_fingerprint IF NOT EXISTS FOR (c:Certificate) REQUIRE c.fingerprint IS UNIQUE",
    "CREATE CONSTRAINT jarm_hash IF NOT EXISTS FOR (j:JARMFingerprint) REQUIRE j.hash IS UNIQUE",
    "CREATE CONSTRAINT favicon_hash IF NOT EXISTS FOR (f:FaviconHash) REQUIRE f.hash IS UNIQUE",
    "CREATE CONSTRAINT cluster_id IF NOT EXISTS FOR (cl:Cluster) REQUIRE cl.cluster_id IS UNIQUE",
    "CREATE CONSTRAINT incident_id IF NOT EXISTS FOR (i:Incident) REQUIRE i.incident_id IS UNIQUE",
    "CREATE CONSTRAINT campaign_id IF NOT EXISTS FOR (ca:Campaign) REQUIRE ca.campaign_id IS UNIQUE",
    "CREATE CONSTRAINT actor_name IF NOT EXISTS FOR (ac:Actor) REQUIRE ac.name IS UNIQUE",
]

ADDITIONAL_INDEXES: Final[list[str]] = [
    "CREATE INDEX domain_tld IF NOT EXISTS FOR (d:Domain) ON (d.tld)",
    "CREATE INDEX domain_first_seen IF NOT EXISTS FOR (d:Domain) ON (d.first_seen)",
    "CREATE INDEX ip_country IF NOT EXISTS FOR (ip:IP) ON (ip.country)",
    "CREATE INDEX cert_issuer IF NOT EXISTS FOR (c:Certificate) ON (c.issuer)",
]

CONSTRAINT_NAMES: Final[frozenset[str]] = frozenset({
    "domain_name", "ip_address", "asn_number", "cert_fingerprint",
    "jarm_hash", "favicon_hash", "cluster_id", "incident_id",
    "campaign_id", "actor_name",
})

INDEX_NAMES: Final[frozenset[str]] = frozenset({
    "domain_tld", "domain_first_seen", "ip_country", "cert_issuer",
})


def init_schema(client: Neo4jClient) -> None:
    for stmt in UNIQUENESS_CONSTRAINTS:
        client.execute_write(stmt)
    for stmt in ADDITIONAL_INDEXES:
        client.execute_write(stmt)
    logger.info(
        "Schema initialized: %d constraints, %d indexes",
        len(UNIQUENESS_CONSTRAINTS),
        len(ADDITIONAL_INDEXES),
    )


def verify_schema(client: Neo4jClient) -> dict[str, bool]:
    result: dict[str, bool] = {}
    existing_constraints: set[str] = set()
    for row in client.execute_read("SHOW CONSTRAINTS"):
        existing_constraints.add(row.get("name", ""))
    for name in CONSTRAINT_NAMES:
        result[name] = name in existing_constraints

    existing_indexes: set[str] = set()
    for row in client.execute_read("SHOW INDEXES"):
        existing_indexes.add(row.get("name", ""))
    for name in INDEX_NAMES:
        result[name] = name in existing_indexes
    return result


def drop_schema(client: Neo4jClient) -> None:
    for name in CONSTRAINT_NAMES:
        client.execute_write(f"DROP CONSTRAINT {name} IF EXISTS")
    for name in INDEX_NAMES:
        client.execute_write(f"DROP INDEX {name} IF EXISTS")
