from __future__ import annotations

from typing import Any

from cti_agent.graph.client import Neo4jClient

QUERY_FULL_ATTRIBUTION_PATH = """
MATCH (d:Domain {name: $domain_name})-[:RESOLVES_TO]->(ip:IP)-[:BELONGS_TO]->(asn:ASN)
OPTIONAL MATCH (d)-[:HAS_CERTIFICATE]->(cert:Certificate)
OPTIONAL MATCH (d)-[:HAS_JARM]->(jarm:JARMFingerprint)
OPTIONAL MATCH (d)-[:HAS_FAVICON]->(fav:FaviconHash)
OPTIONAL MATCH (d)-[:IN_CLUSTER]->(cl:Cluster)
OPTIONAL MATCH (d)-[:PART_OF]->(inc:Incident)-[:BELONGS_TO_CAMPAIGN]->(camp:Campaign)-[:ATTRIBUTED_TO]->(actor:Actor)
RETURN
    d {.*} AS domain,
    collect(DISTINCT ip {.*}) AS ips,
    collect(DISTINCT asn {.*}) AS asns,
    collect(DISTINCT cert {.*}) AS certificates,
    collect(DISTINCT jarm {.*}) AS jarm_fingerprints,
    collect(DISTINCT fav {.*}) AS favicon_hashes,
    collect(DISTINCT cl {.*}) AS clusters,
    collect(DISTINCT inc {.*}) AS incidents,
    collect(DISTINCT camp {.*}) AS campaigns,
    collect(DISTINCT actor {.*}) AS actors
"""

QUERY_SHARED_CERTIFICATE = """
MATCH (d1:Domain {name: $domain_name})-[:HAS_CERTIFICATE]->(cert:Certificate)<-[:HAS_CERTIFICATE]-(d2:Domain)
WHERE d1 <> d2
RETURN d2.name AS related_domain, cert.fingerprint AS cert_fingerprint,
       cert.issuer AS issuer, cert.san_list AS san_list
"""

QUERY_SHARED_JARM = """
MATCH (d1:Domain {name: $domain_name})-[:HAS_JARM]->(jarm:JARMFingerprint)<-[:HAS_JARM]-(d2:Domain)
WHERE d1 <> d2
RETURN d2.name AS related_domain, jarm.hash AS jarm_hash
"""

QUERY_ASN_INCIDENTS = """
MATCH (d:Domain)-[:RESOLVES_TO]->(ip:IP)-[:BELONGS_TO]->(asn:ASN {number: $asn_number})
MATCH (d)-[:PART_OF]->(inc:Incident)
RETURN DISTINCT inc.incident_id AS incident_id, inc.cluster_tag_set AS cluster_tag_set
"""

QUERY_ASN_INCIDENTS_FILTERED = """
MATCH (d:Domain)-[:RESOLVES_TO]->(ip:IP)-[:BELONGS_TO]->(asn:ASN {number: $asn_number})
WHERE NOT asn.is_shared_hosting
MATCH (d)-[:PART_OF]->(inc:Incident)
RETURN DISTINCT inc.incident_id AS incident_id, inc.cluster_tag_set AS cluster_tag_set
"""

QUERY_SHARED_CLUSTER_INCIDENTS = """
MATCH (inc1:Incident {incident_id: $incident_id})
MATCH (d1:Domain)-[:PART_OF]->(inc1)
MATCH (d1)-[:IN_CLUSTER]->(cl:Cluster)<-[:IN_CLUSTER]-(d2:Domain)
MATCH (d2)-[:PART_OF]->(inc2:Incident)
WHERE inc1 <> inc2
RETURN inc2.incident_id AS incident_id, collect(DISTINCT cl.cluster_id) AS shared_clusters
"""

_QUERY_NODE_COUNTS_SIMPLE = """
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC
"""


def get_full_attribution_path(client: Neo4jClient, domain_name: str) -> dict[str, Any]:
    rows = client.execute_read(QUERY_FULL_ATTRIBUTION_PATH, {"domain_name": domain_name})
    if not rows:
        return {}
    return dict(rows[0])


def get_domains_by_shared_certificate(
    client: Neo4jClient, domain_name: str
) -> list[dict[str, Any]]:
    return client.execute_read(QUERY_SHARED_CERTIFICATE, {"domain_name": domain_name})


def get_domains_by_shared_jarm(
    client: Neo4jClient, domain_name: str
) -> list[dict[str, Any]]:
    return client.execute_read(QUERY_SHARED_JARM, {"domain_name": domain_name})


def get_incidents_by_asn(
    client: Neo4jClient,
    asn_number: int,
    *,
    exclude_shared_hosting: bool = True,
) -> list[dict[str, Any]]:
    query = QUERY_ASN_INCIDENTS_FILTERED if exclude_shared_hosting else QUERY_ASN_INCIDENTS
    return client.execute_read(query, {"asn_number": asn_number})


def get_related_incidents(client: Neo4jClient, incident_id: str) -> list[dict[str, Any]]:
    return client.execute_read(QUERY_SHARED_CLUSTER_INCIDENTS, {"incident_id": incident_id})


def count_nodes_by_label(client: Neo4jClient) -> dict[str, int]:
    rows = client.execute_read(_QUERY_NODE_COUNTS_SIMPLE)
    return {row["label"]: row["count"] for row in rows}
