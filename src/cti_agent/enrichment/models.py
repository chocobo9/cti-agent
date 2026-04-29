from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CertificateInfo(BaseModel):
    fingerprint: str | None = None
    serial_number: str | None = None
    issuer: str
    not_before: datetime
    not_after: datetime
    san_list: list[str] = Field(default_factory=list)


class PassiveDNSRecord(BaseModel):
    ip: str
    first_seen: datetime
    last_seen: datetime


class GeoIPInfo(BaseModel):
    ip: str
    asn_number: int | None = None
    asn_name: str | None = None
    country: str | None = None
    city: str | None = None


class DnsQueryResult(BaseModel):
    current_ips: list[str] = Field(default_factory=list)
    dns_record_types: list[str] = Field(default_factory=list)
    has_mx: bool = False
    has_spf: bool = False
    has_dmarc: bool = False


class RdapResult(BaseModel):
    creation_date: date | None = None
    expiration_date: date | None = None
    registrar: str | None = None


class DomainEnrichment(BaseModel):
    model_config = ConfigDict(frozen=True)

    domain: str
    enriched_at: datetime
    certificates: list[CertificateInfo] = Field(default_factory=list)
    jarm_hash: str | None = None
    favicon_hash: int | None = None
    passive_dns: list[PassiveDNSRecord] = Field(default_factory=list)
    current_ips: list[str] = Field(default_factory=list)
    dns_record_types: list[str] = Field(default_factory=list)
    has_mx: bool = False
    has_spf: bool = False
    has_dmarc: bool = False
    creation_date: date | None = None
    expiration_date: date | None = None
    registrar: str | None = None
    geoip: list[GeoIPInfo] = Field(default_factory=list)
    domain_length: int = 0
    domain_entropy: float = 0.0
    tld: str = ""
    errors: dict[str, str] = Field(default_factory=dict)

    def model_dump_json_compatible(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
