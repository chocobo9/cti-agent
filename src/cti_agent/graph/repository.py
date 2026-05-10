from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from datetime import date, datetime
from typing import Self

from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.models import (
    ASNNode,
    ActorNode,
    CampaignNode,
    CertificateNode,
    ClusterNode,
    DomainNode,
    FaviconHashNode,
    IPNode,
    IncidentNode,
    JARMFingerprintNode,
)
from cti_agent.graph.utils import is_shared_hosting_asn

_MERGE_DOMAIN = """
MERGE (d:Domain {name: $name})
ON CREATE SET
    d.tld = $tld, d.length = $length, d.entropy = $entropy,
    d.creation_date = $creation_date, d.registration_length_days = $registration_length_days,
    d.age_days = $age_days, d.has_mx = $has_mx, d.has_spf = $has_spf, d.has_dmarc = $has_dmarc,
    d.dns_record_types = $dns_record_types, d.first_seen = $first_seen, d.last_seen = $last_seen,
    d.decay_score = $decay_score,
    d.source = $source, d.actor = $actor, d.family = $family,
    d.shared_infrastructure = $shared_infrastructure
ON MATCH SET
    d.tld = $tld, d.length = $length, d.entropy = $entropy,
    d.creation_date = coalesce($creation_date, d.creation_date),
    d.registration_length_days = coalesce($registration_length_days, d.registration_length_days),
    d.age_days = coalesce($age_days, d.age_days), d.has_mx = $has_mx, d.has_spf = $has_spf,
    d.has_dmarc = $has_dmarc, d.dns_record_types = $dns_record_types, d.last_seen = $last_seen,
    d.decay_score = $decay_score,
    d.source = coalesce($source, d.source),
    d.actor = coalesce($actor, d.actor),
    d.family = coalesce($family, d.family),
    d.shared_infrastructure = $shared_infrastructure
"""

_MERGE_IP = """
MERGE (ip:IP {address: $address})
ON CREATE SET ip.version = $version, ip.country = $country, ip.city = $city
ON MATCH SET ip.version = $version, ip.country = coalesce($country, ip.country), ip.city = coalesce($city, ip.city)
"""

_MERGE_ASN = """
MERGE (a:ASN {number: $number})
ON CREATE SET a.name = $name, a.country = $country, a.is_shared_hosting = $is_shared_hosting
ON MATCH SET a.name = coalesce($name, a.name), a.country = coalesce($country, a.country), a.is_shared_hosting = $is_shared_hosting
"""

_MERGE_CERTIFICATE = """
MERGE (c:Certificate {fingerprint: $fingerprint})
ON CREATE SET c.issuer = $issuer, c.not_before = $not_before, c.not_after = $not_after, c.san_list = $san_list, c.san_count = $san_count, c.key_type = $key_type
ON MATCH SET c.issuer = coalesce($issuer, c.issuer), c.not_before = coalesce($not_before, c.not_before), c.not_after = coalesce($not_after, c.not_after), c.san_list = $san_list, c.san_count = $san_count, c.key_type = coalesce($key_type, c.key_type)
"""

_MERGE_JARM = "MERGE (j:JARMFingerprint {hash: $hash})"
_MERGE_FAVICON = "MERGE (f:FaviconHash {hash: $hash})"
_MERGE_CLUSTER = """
MERGE (cl:Cluster {cluster_id: $cluster_id})
ON CREATE SET cl.size = $size, cl.quality_score = $quality_score, cl.algorithm = $algorithm
ON MATCH SET cl.size = $size, cl.quality_score = coalesce($quality_score, cl.quality_score), cl.algorithm = $algorithm
"""
_MERGE_INCIDENT = """
MERGE (i:Incident {incident_id: $incident_id})
ON CREATE SET i.date = $date, i.cluster_tag_set = $cluster_tag_set, i.domain_count = $domain_count
ON MATCH SET i.date = $date, i.cluster_tag_set = $cluster_tag_set, i.domain_count = $domain_count
"""
_MERGE_CAMPAIGN = """
MERGE (ca:Campaign {campaign_id: $campaign_id})
ON CREATE SET ca.name = $name, ca.confidence_score = $confidence_score, ca.first_seen = $first_seen, ca.last_seen = $last_seen
ON MATCH SET ca.name = $name, ca.confidence_score = $confidence_score, ca.first_seen = coalesce($first_seen, ca.first_seen), ca.last_seen = $last_seen
"""
_MERGE_ACTOR = """
MERGE (ac:Actor {name: $name})
ON CREATE SET ac.aliases = $aliases, ac.country = $country
ON MATCH SET ac.aliases = $aliases, ac.country = coalesce($country, ac.country)
"""

_MERGE_RESOLVES_TO = """
MATCH (d:Domain {name: $domain}) MATCH (ip:IP {address: $ip})
MERGE (d)-[r:RESOLVES_TO]->(ip)
ON CREATE SET r.first_seen = $first_seen, r.last_seen = $last_seen
ON MATCH SET r.last_seen = CASE WHEN $last_seen > r.last_seen THEN $last_seen ELSE r.last_seen END
"""
_MERGE_BELONGS_TO = "MATCH (ip:IP {address: $ip}) MATCH (a:ASN {number: $asn_number}) MERGE (ip)-[:BELONGS_TO]->(a)"
_MERGE_HAS_CERTIFICATE = "MATCH (d:Domain {name: $domain}) MATCH (c:Certificate {fingerprint: $cert_fingerprint}) MERGE (d)-[r:HAS_CERTIFICATE]->(c) ON CREATE SET r.first_seen = $first_seen"
_MERGE_HAS_JARM = "MATCH (d:Domain {name: $domain}) MATCH (j:JARMFingerprint {hash: $jarm_hash}) MERGE (d)-[r:HAS_JARM]->(j) ON CREATE SET r.scan_date = $scan_date"
_MERGE_HAS_FAVICON = "MATCH (d:Domain {name: $domain}) MATCH (f:FaviconHash {hash: $favicon_hash}) MERGE (d)-[r:HAS_FAVICON]->(f) ON CREATE SET r.scan_date = $scan_date"
_MERGE_IN_CLUSTER = "MATCH (d:Domain {name: $domain}) MATCH (cl:Cluster {cluster_id: $cluster_id}) MERGE (d)-[:IN_CLUSTER]->(cl)"
_MERGE_PART_OF = "MATCH (d:Domain {name: $domain}) MATCH (i:Incident {incident_id: $incident_id}) MERGE (d)-[:PART_OF]->(i)"
_MERGE_BELONGS_TO_CAMPAIGN = "MATCH (i:Incident {incident_id: $incident_id}) MATCH (ca:Campaign {campaign_id: $campaign_id}) MERGE (i)-[:BELONGS_TO_CAMPAIGN]->(ca)"
_MERGE_ATTRIBUTED_TO = "MATCH (ca:Campaign {campaign_id: $campaign_id}) MATCH (ac:Actor {name: $actor_name}) MERGE (ca)-[r:ATTRIBUTED_TO]->(ac) ON CREATE SET r.confidence = $confidence, r.evidence_summary = $evidence_summary ON MATCH SET r.confidence = $confidence, r.evidence_summary = $evidence_summary"

_GET_DOMAIN = "MATCH (d:Domain {name: $name}) RETURN d {.*} AS props"
_DOMAIN_EXISTS = "MATCH (d:Domain {name: $name}) RETURN count(d) > 0 AS exists"
_UPDATE_DOMAIN_TIMESTAMPS = "MATCH (d:Domain {name: $name}) SET d.last_seen = $last_seen, d.decay_score = $decay_score"
_UPDATE_IP_GEO = "MATCH (ip:IP {address: $address}) SET ip.country = coalesce($country, ip.country), ip.city = coalesce($city, ip.city)"


class GraphRepository:
    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    def transaction(self) -> AbstractContextManager[Self]:
        # Each execute_write already runs in its own Neo4j transaction.
        # This context exists to satisfy the batch-ingestion API and to act as
        # a grouping boundary for try/except in pipeline.ingest_batch.
        return nullcontext(self)

    def merge_domain(
        self,
        *,
        name: str,
        tld: str,
        length: int,
        entropy: float,
        creation_date: date | None = None,
        registration_length_days: int | None = None,
        age_days: int | None = None,
        has_mx: bool = False,
        has_spf: bool = False,
        has_dmarc: bool = False,
        dns_record_types: list[str] | None = None,
        first_seen: datetime | None = None,
        last_seen: datetime | None = None,
        decay_score: float = 1.0,
        source: str | None = None,
        actor: str | None = None,
        family: str | None = None,
        shared_infrastructure: bool = False,
    ) -> None:
        node = DomainNode(
            name=name,
            tld=tld,
            length=length,
            entropy=entropy,
            creation_date=creation_date,
            registration_length_days=registration_length_days,
            age_days=age_days,
            has_mx=has_mx,
            has_spf=has_spf,
            has_dmarc=has_dmarc,
            dns_record_types=list(dns_record_types) if dns_record_types else [],
            first_seen=first_seen,
            last_seen=last_seen,
            decay_score=decay_score,
            source=source,
            actor=actor,
            family=family,
            shared_infrastructure=shared_infrastructure,
        )
        self._client.execute_write(_MERGE_DOMAIN, node.to_dict())

    def merge_ip(self, *, address: str, version: int, country: str | None = None, city: str | None = None) -> None:
        node = IPNode(address=address, version=version, country=country, city=city)  # type: ignore[arg-type]
        self._client.execute_write(_MERGE_IP, node.to_dict())

    def merge_asn(self, *, number: int, name: str | None = None, country: str | None = None) -> None:
        # Normalize missing ASN names to a stable AS{number} placeholder so the
        # downstream Pydantic model stays valid regardless of GeoIP coverage.
        normalized_name = name if name else f"AS{number}"
        node = ASNNode(
            number=number,
            name=normalized_name,
            country=country,
            is_shared_hosting=is_shared_hosting_asn(number),
        )
        self._client.execute_write(_MERGE_ASN, node.to_dict())

    def merge_certificate(
        self,
        *,
        fingerprint: str,
        issuer: str,
        not_before: date | None = None,
        not_after: date | None = None,
        san_list: list[str] | None = None,
        san_count: int = 0,
        key_type: str | None = None,
    ) -> None:
        node = CertificateNode(
            fingerprint=fingerprint,
            issuer=issuer,
            not_before=not_before,
            not_after=not_after,
            san_list=list(san_list) if san_list else [],
            san_count=san_count,
            key_type=key_type,
        )
        self._client.execute_write(_MERGE_CERTIFICATE, node.to_dict())

    def merge_jarm(self, *, hash: str) -> None:
        self._client.execute_write(_MERGE_JARM, JARMFingerprintNode(hash=hash).to_dict())

    def merge_favicon(self, *, hash: str) -> None:
        self._client.execute_write(_MERGE_FAVICON, FaviconHashNode(hash=hash).to_dict())

    def merge_cluster(self, *, cluster_id: int, size: int, algorithm: str, quality_score: float | None = None) -> None:
        self._client.execute_write(_MERGE_CLUSTER, ClusterNode(cluster_id=cluster_id, size=size, algorithm=algorithm, quality_score=quality_score).to_dict())

    def merge_incident(self, *, incident_id: str, date: date, cluster_tag_set: list[int] | None = None, domain_count: int = 0) -> None:
        self._client.execute_write(_MERGE_INCIDENT, IncidentNode(incident_id=incident_id, date=date, cluster_tag_set=cluster_tag_set or [], domain_count=domain_count).to_dict())

    def merge_campaign(
        self,
        *,
        campaign_id: str,
        name: str,
        confidence_score: float = 0.0,
        first_seen: date | None = None,
        last_seen: date | None = None,
    ) -> None:
        node = CampaignNode(
            campaign_id=campaign_id,
            name=name,
            confidence_score=confidence_score,
            first_seen=first_seen,
            last_seen=last_seen,
        )
        self._client.execute_write(_MERGE_CAMPAIGN, node.to_dict())

    def merge_actor(self, *, name: str, aliases: list[str] | None = None, country: str | None = None) -> None:
        self._client.execute_write(_MERGE_ACTOR, ActorNode(name=name, aliases=aliases or [], country=country).to_dict())

    def merge_resolves_to(
        self,
        *,
        domain: str,
        ip: str,
        first_seen: datetime,
        last_seen: datetime,
    ) -> None:
        self._client.execute_write(
            _MERGE_RESOLVES_TO,
            {"domain": domain, "ip": ip, "first_seen": first_seen, "last_seen": last_seen},
        )

    def merge_belongs_to(self, *, ip: str, asn_number: int) -> None:
        self._client.execute_write(_MERGE_BELONGS_TO, {"ip": ip, "asn_number": asn_number})

    def merge_has_certificate(
        self,
        *,
        domain: str,
        cert_fingerprint: str,
        first_seen: datetime | None = None,
    ) -> None:
        self._client.execute_write(
            _MERGE_HAS_CERTIFICATE,
            {"domain": domain, "cert_fingerprint": cert_fingerprint, "first_seen": first_seen},
        )

    def merge_has_jarm(
        self,
        *,
        domain: str,
        jarm_hash: str,
        scan_date: datetime | None = None,
    ) -> None:
        self._client.execute_write(
            _MERGE_HAS_JARM,
            {"domain": domain, "jarm_hash": jarm_hash, "scan_date": scan_date},
        )

    def merge_has_favicon(
        self,
        *,
        domain: str,
        favicon_hash: str,
        scan_date: datetime | None = None,
    ) -> None:
        self._client.execute_write(
            _MERGE_HAS_FAVICON,
            {"domain": domain, "favicon_hash": favicon_hash, "scan_date": scan_date},
        )

    def merge_in_cluster(self, *, domain: str, cluster_id: int) -> None:
        self._client.execute_write(_MERGE_IN_CLUSTER, {"domain": domain, "cluster_id": cluster_id})

    def merge_part_of(self, *, domain: str, incident_id: str) -> None:
        self._client.execute_write(_MERGE_PART_OF, {"domain": domain, "incident_id": incident_id})

    def merge_belongs_to_campaign(self, *, incident_id: str, campaign_id: str) -> None:
        self._client.execute_write(_MERGE_BELONGS_TO_CAMPAIGN, {"incident_id": incident_id, "campaign_id": campaign_id})

    def merge_attributed_to(
        self,
        *,
        campaign_id: str,
        actor_name: str,
        confidence: float,
        evidence_summary: str | None = None,
    ) -> None:
        self._client.execute_write(
            _MERGE_ATTRIBUTED_TO,
            {
                "campaign_id": campaign_id,
                "actor_name": actor_name,
                "confidence": confidence,
                "evidence_summary": evidence_summary,
            },
        )

    def get_domain(self, name: str) -> DomainNode | None:
        rows = self._client.execute_read(_GET_DOMAIN, {"name": name})
        return None if not rows else DomainNode.from_record(rows[0]["props"])

    def domain_exists(self, name: str) -> bool:
        rows = self._client.execute_read(_DOMAIN_EXISTS, {"name": name})
        return bool(rows and rows[0]["exists"])

    def update_domain_timestamps(self, *, name: str, last_seen: datetime, decay_score: float) -> None:
        self._client.execute_write(_UPDATE_DOMAIN_TIMESTAMPS, {"name": name, "last_seen": last_seen, "decay_score": decay_score})

    def update_ip_geo(self, *, address: str, country: str | None = None, city: str | None = None) -> None:
        self._client.execute_write(_UPDATE_IP_GEO, {"address": address, "country": country, "city": city})
