from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from cti_agent.ingestion.models import DomainEnrichment
from cti_agent.ingestion.utils import compute_cert_key, compute_reg_length, detect_ip_version


@dataclass(frozen=True)
class DomainProps:
    name: str
    tld: str
    length: int
    entropy: float
    creation_date: object
    registration_length_days: int | None
    has_mx: bool
    has_spf: bool
    has_dmarc: bool
    dns_record_types: list[str]
    first_seen: datetime
    last_seen: datetime
    decay_score: float


@dataclass(frozen=True)
class CertificateOp:
    key: str
    issuer: str
    not_before: datetime
    not_after: datetime
    san_list: list[str]
    san_count: int


@dataclass(frozen=True)
class JarmOp:
    hash: str
    scan_date: datetime


@dataclass(frozen=True)
class FaviconOp:
    hash: str
    scan_date: datetime


@dataclass(frozen=True)
class IpOp:
    address: str
    version: int
    first_seen: datetime
    last_seen: datetime
    country: str | None = None
    city: str | None = None
    asn_number: int | None = None


@dataclass(frozen=True)
class AsnOp:
    number: int
    name: str | None
    country: str | None
    ip_addresses: list[str] = field(default_factory=list)


def map_domain_props(enrichment: DomainEnrichment) -> DomainProps:
    return DomainProps(
        name=enrichment.domain,
        tld=enrichment.tld,
        length=enrichment.domain_length,
        entropy=enrichment.domain_entropy,
        creation_date=enrichment.creation_date,
        registration_length_days=compute_reg_length(enrichment.creation_date, enrichment.expiration_date),
        has_mx=enrichment.has_mx,
        has_spf=enrichment.has_spf,
        has_dmarc=enrichment.has_dmarc,
        dns_record_types=list(enrichment.dns_record_types),
        first_seen=enrichment.enriched_at,
        last_seen=enrichment.enriched_at,
        decay_score=1.0,
    )


def map_certificate_ops(enrichment: DomainEnrichment) -> list[CertificateOp]:
    ops: list[CertificateOp] = []
    for cert in enrichment.certificates:
        key = compute_cert_key(cert.fingerprint, cert.serial_number, cert.issuer)
        ops.append(CertificateOp(key=key, issuer=cert.issuer, not_before=cert.not_before, not_after=cert.not_after, san_list=list(cert.san_list), san_count=len(cert.san_list)))
    return ops


def map_jarm_op(enrichment: DomainEnrichment) -> JarmOp | None:
    if enrichment.jarm_hash is None:
        return None
    return JarmOp(hash=enrichment.jarm_hash, scan_date=enrichment.enriched_at)


def map_favicon_op(enrichment: DomainEnrichment) -> FaviconOp | None:
    if enrichment.favicon_hash is None:
        return None
    return FaviconOp(hash=str(enrichment.favicon_hash), scan_date=enrichment.enriched_at)


def map_ip_ops(enrichment: DomainEnrichment) -> list[IpOp]:
    seen: set[str] = set()
    ops: list[IpOp] = []
    pdns_map = {p.ip: p for p in enrichment.passive_dns}
    geo_map = {g.ip: g for g in enrichment.geoip}
    all_ips = list(enrichment.current_ips)
    for p in enrichment.passive_dns:
        if p.ip not in {ip for ip in all_ips}:
            all_ips.append(p.ip)
    for ip_addr in all_ips:
        if ip_addr in seen:
            continue
        seen.add(ip_addr)
        pdns = pdns_map.get(ip_addr)
        geo = geo_map.get(ip_addr)
        ops.append(IpOp(address=ip_addr, version=detect_ip_version(ip_addr), first_seen=pdns.first_seen if pdns else enrichment.enriched_at, last_seen=pdns.last_seen if pdns else enrichment.enriched_at, country=geo.country if geo else None, city=geo.city if geo else None, asn_number=geo.asn_number if geo else None))
    return ops


def map_asn_ops(enrichment: DomainEnrichment) -> list[AsnOp]:
    asn_ips: dict[int, list[str]] = {}
    asn_meta: dict[int, tuple[str | None, str | None]] = {}
    for geo in enrichment.geoip:
        if geo.asn_number is None:
            continue
        asn_ips.setdefault(geo.asn_number, []).append(geo.ip)
        if geo.asn_number not in asn_meta:
            asn_meta[geo.asn_number] = (geo.asn_name, geo.country)
    ops: list[AsnOp] = []
    for asn_num, ips in asn_ips.items():
        name, country = asn_meta[asn_num]
        ops.append(AsnOp(number=asn_num, name=name, country=country, ip_addresses=ips))
    return ops
