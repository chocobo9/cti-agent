from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict


class _NodeBase(BaseModel):
    model_config = ConfigDict(frozen=True)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict suitable for Cypher parameters."""
        return self.model_dump(mode="python")

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Self:
        """Deserialize from a Neo4j result record."""
        converted = {}
        for key, value in record.items():
            if hasattr(value, "iso_format"):
                converted[key] = value.iso_format()
            else:
                converted[key] = value
        return cls.model_validate(converted)


class DomainNode(_NodeBase):
    name: str
    tld: str
    length: int
    entropy: float
    creation_date: date | None = None
    registration_length_days: int | None = None
    age_days: int | None = None
    has_mx: bool = False
    has_spf: bool = False
    has_dmarc: bool = False
    dns_record_types: list[str] = []
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    decay_score: float = 1.0
    source: str | None = None
    actor: str | None = None
    family: str | None = None
    shared_infrastructure: bool = False


class IPNode(_NodeBase):
    address: str
    version: Literal[4, 6]
    country: str | None = None
    city: str | None = None


class ASNNode(_NodeBase):
    number: int
    name: str
    country: str | None = None
    is_shared_hosting: bool = False


class CertificateNode(_NodeBase):
    fingerprint: str
    issuer: str
    not_before: date | None = None
    not_after: date | None = None
    san_list: list[str] = []
    san_count: int = 0
    key_type: str | None = None


class JARMFingerprintNode(_NodeBase):
    hash: str


class FaviconHashNode(_NodeBase):
    hash: str


class ClusterNode(_NodeBase):
    cluster_id: int
    size: int
    quality_score: float | None = None
    algorithm: str


class IncidentNode(_NodeBase):
    incident_id: str
    date: date
    cluster_tag_set: list[int] = []
    domain_count: int = 0


class CampaignNode(_NodeBase):
    campaign_id: str
    name: str
    confidence_score: float = 0.0
    first_seen: date | None = None
    last_seen: date | None = None


class ActorNode(_NodeBase):
    name: str
    aliases: list[str] = []
    country: str | None = None


class ResolvesToRel(_NodeBase):
    first_seen: datetime
    last_seen: datetime


class HasCertificateRel(_NodeBase):
    first_seen: datetime | None = None


class HasJARMRel(_NodeBase):
    scan_date: datetime | None = None


class HasFaviconRel(_NodeBase):
    scan_date: datetime | None = None


class AttributedToRel(_NodeBase):
    confidence: float
    evidence_summary: str | None = None
