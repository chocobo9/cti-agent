"""Eight parameterized Cypher query templates for the CTI attribution agent.

Task 4.2: Each method builds a parameterized Cypher query, executes it via
Neo4jClient, and returns a compressed dict.  Templates use ATTRIBUTED_TO
edges only — GROUND_TRUTH_ATTRIBUTION is strictly for evaluation.

Graph edge inventory (from repository.py):
    Domain -[RESOLVES_TO]-> IP -[BELONGS_TO]-> ASN
    Domain -[HAS_CERTIFICATE]-> Certificate
    Domain -[HAS_JARM]-> JARMFingerprint
    Domain -[HAS_FAVICON]-> FaviconHash
    Domain -[IN_CLUSTER]-> Cluster
    Domain -[PART_OF]-> Incident -[BELONGS_TO_CAMPAIGN]-> Campaign
    Campaign -[ATTRIBUTED_TO]-> Actor
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from cti_agent.graph.client import Neo4jClient

logger = logging.getLogger(__name__)


class CypherTemplateExecutor:
    """Executes the 8 parameterized Cypher templates against Neo4j."""

    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # T1: domain_infrastructure
    # ------------------------------------------------------------------

    _T1_QUERY = """
    MATCH (d:Domain {name: $domain})
    OPTIONAL MATCH (d)-[:RESOLVES_TO]->(ip:IP)
    OPTIONAL MATCH (ip)-[:BELONGS_TO]->(asn:ASN)
    OPTIONAL MATCH (d)-[:HAS_CERTIFICATE]->(cert:Certificate)
    OPTIONAL MATCH (d)-[:HAS_JARM]->(jarm:JARMFingerprint)
    OPTIONAL MATCH (d)-[:HAS_FAVICON]->(fav:FaviconHash)
    RETURN
        d {.name, .first_seen, .shared_infrastructure, .decay_score} AS domain,
        collect(DISTINCT ip {.address, .country}) AS ips,
        collect(DISTINCT asn {.number, .name, .is_shared_hosting}) AS asns,
        collect(DISTINCT cert {.fingerprint, .issuer, .san_list, .not_before, .not_after}) AS certificates,
        collect(DISTINCT jarm {.hash}) AS jarm,
        collect(DISTINCT fav {.hash}) AS favicon
    """

    def domain_infrastructure(self, domain: str) -> dict[str, Any]:
        """T1: Full infrastructure profile of a domain."""
        try:
            rows = self._client.execute_read(self._T1_QUERY, {"domain": domain})
        except Exception:
            logger.exception("T1 domain_infrastructure failed for %s", domain)
            return {"domain": None, "ips": [], "asns": [], "certificates": [], "jarm": [], "favicon": []}
        if not rows:
            return {"domain": None, "ips": [], "asns": [], "certificates": [], "jarm": [], "favicon": []}
        return dict(rows[0])

    # ------------------------------------------------------------------
    # T2: domain_to_actor
    # ------------------------------------------------------------------

    _T2_QUERY = """
    MATCH (d:Domain {name: $domain})
    OPTIONAL MATCH (d)-[:IN_CLUSTER]->(cl:Cluster)
    OPTIONAL MATCH (d)-[:PART_OF]->(inc:Incident)
    OPTIONAL MATCH (inc)-[:BELONGS_TO_CAMPAIGN]->(ca:Campaign)
    OPTIONAL MATCH (ca)-[:ATTRIBUTED_TO]->(ac:Actor)
    RETURN
        d {.name, .first_seen, .shared_infrastructure} AS domain,
        collect(DISTINCT cl {.cluster_id, .size, .algorithm}) AS clusters,
        collect(DISTINCT inc {.incident_id, .date, .cluster_tag_set}) AS incidents,
        collect(DISTINCT ca {.campaign_id, .name, .confidence_score, .first_seen, .last_seen}) AS campaigns,
        collect(DISTINCT ac {.name, .aliases}) AS actors
    """

    def domain_to_actor(self, domain: str) -> dict[str, Any]:
        """T2: Core attribution chain — Domain → Cluster, Domain → Incident → Campaign → Actor."""
        try:
            rows = self._client.execute_read(self._T2_QUERY, {"domain": domain})
        except Exception:
            logger.exception("T2 domain_to_actor failed for %s", domain)
            return {"domain": None, "clusters": [], "incidents": [], "campaigns": [], "actors": [], "cluster_tag_set": []}
        if not rows:
            return {"domain": None, "clusters": [], "incidents": [], "campaigns": [], "actors": [], "cluster_tag_set": []}
        row = dict(rows[0])
        tag_sets: list[list[int]] = [
            inc["cluster_tag_set"]
            for inc in row.get("incidents", [])
            if inc.get("cluster_tag_set")
        ]
        row["cluster_tag_set"] = sorted({t for ts in tag_sets for t in ts})
        return row

    # ------------------------------------------------------------------
    # T3: actor_to_domains
    # ------------------------------------------------------------------

    _T3_QUERY = """
    MATCH (ac:Actor {name: $actor})<-[:ATTRIBUTED_TO]-(ca:Campaign)
          <-[:BELONGS_TO_CAMPAIGN]-(inc:Incident)<-[:PART_OF]-(d:Domain)
    OPTIONAL MATCH (d)-[:IN_CLUSTER]->(cl:Cluster)
    RETURN
        ac {.name, .aliases} AS actor,
        collect(DISTINCT ca {.campaign_id, .name, .first_seen, .last_seen}) AS campaigns,
        collect(DISTINCT inc {.incident_id, .date, .cluster_tag_set}) AS incidents,
        collect(DISTINCT d {.name, .first_seen, .shared_infrastructure}) AS domains,
        collect(DISTINCT cl {.cluster_id, .size, .algorithm}) AS clusters
    """

    def actor_to_domains(self, actor: str) -> dict[str, Any]:
        """T3: Reverse lookup — Actor → Campaign → Incident ← Domain → Cluster."""
        try:
            rows = self._client.execute_read(self._T3_QUERY, {"actor": actor})
        except Exception:
            logger.exception("T3 actor_to_domains failed for %s", actor)
            return {"actor": None, "campaigns": [], "incidents": [], "domains": [], "clusters": []}
        if not rows:
            return {"actor": None, "campaigns": [], "incidents": [], "domains": [], "clusters": []}
        return dict(rows[0])

    # ------------------------------------------------------------------
    # T4: shared_infrastructure
    # ------------------------------------------------------------------

    _T4_QUERY = """
    MATCH (d1:Domain {name: $domain})-[:RESOLVES_TO]->(ip:IP)<-[:RESOLVES_TO]-(d2:Domain)
    WHERE d1 <> d2
    OPTIONAL MATCH (ip)-[:BELONGS_TO]->(asn:ASN)
    WITH d1, d2, ip, asn
    WHERE asn IS NULL OR NOT asn.is_shared_hosting
    RETURN
        d1 {.name} AS domain,
        collect(DISTINCT d2 {.name, .first_seen, .shared_infrastructure}) AS shared_domains,
        collect(DISTINCT ip {.address, .country}) AS shared_ips,
        collect(DISTINCT asn {.number, .name}) AS shared_asns
    """

    def shared_infrastructure(self, domain: str) -> dict[str, Any]:
        """T4: Co-hosted domains sharing non-shared-hosting infrastructure."""
        try:
            rows = self._client.execute_read(self._T4_QUERY, {"domain": domain})
        except Exception:
            logger.exception("T4 shared_infrastructure failed for %s", domain)
            return {"domain": None, "shared_domains": [], "shared_ips": [], "shared_asns": []}
        if not rows:
            return {"domain": None, "shared_domains": [], "shared_ips": [], "shared_asns": []}
        return dict(rows[0])

    # ------------------------------------------------------------------
    # T5: certificate_pivot
    # ------------------------------------------------------------------

    _T5_QUERY = """
    MATCH (d1:Domain {name: $domain})-[:HAS_CERTIFICATE]->(cert:Certificate)
          <-[:HAS_CERTIFICATE]-(d2:Domain)
    WHERE d1 <> d2
    RETURN
        d1 {.name} AS domain,
        collect(DISTINCT d2 {.name, .first_seen}) AS related_domains,
        collect(DISTINCT cert {.fingerprint, .issuer, .san_list}) AS shared_certificates
    """

    def certificate_pivot(self, domain: str) -> dict[str, Any]:
        """T5: Domains sharing TLS certificates."""
        try:
            rows = self._client.execute_read(self._T5_QUERY, {"domain": domain})
        except Exception:
            logger.exception("T5 certificate_pivot failed for %s", domain)
            return {"domain": None, "related_domains": [], "shared_certificates": []}
        if not rows:
            return {"domain": None, "related_domains": [], "shared_certificates": []}
        return dict(rows[0])

    # ------------------------------------------------------------------
    # T6: reverse_ip_lookup
    # ------------------------------------------------------------------

    _T6_IP_QUERY = """
    MATCH (ip:IP {address: $ip})<-[:RESOLVES_TO]-(d:Domain)
    OPTIONAL MATCH (ip)-[:BELONGS_TO]->(asn:ASN)
    WITH ip, d, asn
    WHERE asn IS NULL OR NOT asn.is_shared_hosting
    RETURN
        ip {.address, .country} AS target,
        collect(DISTINCT d {.name, .first_seen, .shared_infrastructure}) AS domains
    """

    _T6_ASN_QUERY = """
    MATCH (asn:ASN {number: $asn_number})
    WHERE NOT asn.is_shared_hosting
    MATCH (asn)<-[:BELONGS_TO]-(ip:IP)<-[:RESOLVES_TO]-(d:Domain)
    RETURN
        asn {.number, .name} AS target,
        collect(DISTINCT d {.name, .first_seen, .shared_infrastructure}) AS domains
    """

    def reverse_ip_lookup(
        self, *, ip: str | None = None, asn_number: int | None = None
    ) -> dict[str, Any]:
        """T6: Reverse lookup from IP or ASN to domains.  Excludes shared hosting."""
        try:
            if ip is not None:
                rows = self._client.execute_read(self._T6_IP_QUERY, {"ip": ip})
            elif asn_number is not None:
                rows = self._client.execute_read(self._T6_ASN_QUERY, {"asn_number": asn_number})
            else:
                return {"target": None, "domains": []}
        except Exception:
            logger.exception("T6 reverse_ip_lookup failed for ip=%s asn=%s", ip, asn_number)
            return {"target": None, "domains": []}
        if not rows:
            return {"target": None, "domains": []}
        return dict(rows[0])

    # ------------------------------------------------------------------
    # T7: similar_incidents
    # ------------------------------------------------------------------

    _T7_FETCH_ALL_INCIDENTS = """
    MATCH (inc:Incident)
    WHERE size(inc.cluster_tag_set) > 0
    RETURN inc.incident_id AS incident_id,
           inc.cluster_tag_set AS cluster_tag_set,
           inc.date AS date
    """

    def similar_incidents(
        self, cluster_tag_set: list[int], *, top_k: int = 10
    ) -> dict[str, Any]:
        """T7: Find incidents with similar cluster tag sets via Jaccard.

        Data source: Incident.cluster_tag_set (list[int]) stored on Incident
        nodes in Neo4j.  Jaccard is computed in Python because Cypher lacks
        native set-intersection on list properties.
        """
        if not cluster_tag_set:
            return {"source_tag_set": [], "similar_incidents": []}

        try:
            rows = self._client.execute_read(self._T7_FETCH_ALL_INCIDENTS)
        except Exception:
            logger.exception("T7 similar_incidents failed")
            return {"source_tag_set": cluster_tag_set, "similar_incidents": []}

        source_set = set(cluster_tag_set)
        scored: list[dict[str, Any]] = []
        for row in rows:
            other_set = set(row["cluster_tag_set"])
            if other_set == source_set:
                continue
            union = source_set | other_set
            if not union:
                continue
            jaccard = len(source_set & other_set) / len(union)
            if jaccard > 0:
                scored.append({
                    "incident_id": row["incident_id"],
                    "cluster_tag_set": row["cluster_tag_set"],
                    "date": row["date"],
                    "jaccard_similarity": round(jaccard, 4),
                })

        scored.sort(key=lambda x: x["jaccard_similarity"], reverse=True)
        return {
            "source_tag_set": cluster_tag_set,
            "similar_incidents": scored[:top_k],
        }

    # ------------------------------------------------------------------
    # T8: active_campaigns
    # ------------------------------------------------------------------

    _T8_BY_ACTOR_QUERY = """
    MATCH (ac:Actor {name: $actor})<-[:ATTRIBUTED_TO]-(ca:Campaign)
    OPTIONAL MATCH (ca)<-[:BELONGS_TO_CAMPAIGN]-(inc:Incident)<-[:PART_OF]-(d:Domain)
    RETURN
        collect(DISTINCT ca {.campaign_id, .name, .confidence_score, .first_seen, .last_seen}) AS campaigns,
        collect(DISTINCT ac {.name, .aliases}) AS actors,
        collect(DISTINCT d {.name, .first_seen}) AS domains
    """

    _T8_BY_TIME_QUERY = """
    MATCH (ca:Campaign)
    WHERE ca.last_seen >= $start AND ca.first_seen <= $end
    OPTIONAL MATCH (ca)-[:ATTRIBUTED_TO]->(ac:Actor)
    OPTIONAL MATCH (ca)<-[:BELONGS_TO_CAMPAIGN]-(inc:Incident)<-[:PART_OF]-(d:Domain)
    RETURN
        collect(DISTINCT ca {.campaign_id, .name, .confidence_score, .first_seen, .last_seen}) AS campaigns,
        collect(DISTINCT ac {.name, .aliases}) AS actors,
        collect(DISTINCT d {.name, .first_seen}) AS domains
    """

    def active_campaigns(
        self,
        *,
        actor: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, Any]:
        """T8: Active campaigns by actor name or time range."""
        try:
            if actor is not None:
                rows = self._client.execute_read(
                    self._T8_BY_ACTOR_QUERY, {"actor": actor}
                )
            elif start is not None and end is not None:
                rows = self._client.execute_read(
                    self._T8_BY_TIME_QUERY, {"start": start, "end": end}
                )
            else:
                return {"campaigns": [], "actors": [], "domains": []}
        except Exception:
            logger.exception("T8 active_campaigns failed")
            return {"campaigns": [], "actors": [], "domains": []}
        if not rows:
            return {"campaigns": [], "actors": [], "domains": []}
        return dict(rows[0])
