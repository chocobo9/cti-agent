from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from cti_agent.enrichment.config import get_settings
from cti_agent.enrichment.ct_logs import query_crt_sh
from cti_agent.enrichment.domain_features import compute_domain_string_features
from cti_agent.enrichment.favicon import get_favicon_hash
from cti_agent.enrichment.geoip import lookup_geoip_batch
from cti_agent.enrichment.jarm_scanner import scan_jarm
from cti_agent.enrichment.models import (
    CertificateInfo,
    DnsQueryResult,
    DomainEnrichment,
    GeoIPInfo,
    PassiveDNSRecord,
    RdapResult,
)
from cti_agent.enrichment.passive_dns import query_dns_records, query_passive_dns
from cti_agent.enrichment.rdap import query_rdap


async def enrich_domain(domain: str) -> DomainEnrichment:
    errors: dict[str, str] = {}
    results = await asyncio.gather(
        query_crt_sh(domain),
        scan_jarm(domain),
        get_favicon_hash(domain),
        query_passive_dns(domain),
        query_rdap(domain),
        query_dns_records(domain),
        return_exceptions=True,
    )

    def _extract(idx: int, name: str, default: object) -> object:
        val = results[idx]
        if isinstance(val, BaseException):
            errors[name] = f"{type(val).__name__}: {val}"
            return default
        return val

    certificates: list[CertificateInfo] = _extract(0, "ct_logs", [])  # type: ignore[assignment]
    jarm_hash: str | None = _extract(1, "jarm", None)  # type: ignore[assignment]
    favicon_hash_val: int | None = _extract(2, "favicon", None)  # type: ignore[assignment]
    passive_dns: list[PassiveDNSRecord] = _extract(3, "passive_dns", [])  # type: ignore[assignment]
    rdap_result: RdapResult = _extract(4, "rdap", RdapResult())  # type: ignore[assignment]
    dns_result: DnsQueryResult = _extract(5, "dns", DnsQueryResult())  # type: ignore[assignment]

    all_ips: list[str] = []
    for record in passive_dns:
        if record.ip not in all_ips:
            all_ips.append(record.ip)
    for ip in dns_result.current_ips:
        if ip not in all_ips:
            all_ips.append(ip)

    geoip: list[GeoIPInfo] = []
    if all_ips:
        try:
            geoip = lookup_geoip_batch(all_ips)
        except Exception as exc:
            errors["geoip"] = f"{type(exc).__name__}: {exc}"

    features = compute_domain_string_features(domain)
    return DomainEnrichment(
        domain=domain,
        enriched_at=datetime.now(UTC),
        certificates=certificates,
        jarm_hash=jarm_hash,
        favicon_hash=favicon_hash_val,
        passive_dns=passive_dns,
        current_ips=dns_result.current_ips,
        dns_record_types=dns_result.dns_record_types,
        has_mx=dns_result.has_mx,
        has_spf=dns_result.has_spf,
        has_dmarc=dns_result.has_dmarc,
        creation_date=rdap_result.creation_date,
        expiration_date=rdap_result.expiration_date,
        registrar=rdap_result.registrar,
        geoip=geoip,
        domain_length=features.domain_length,
        domain_entropy=features.domain_entropy,
        tld=features.tld,
        errors=errors,
    )


async def enrich_batch(domains: list[str], concurrency: int | None = None) -> list[DomainEnrichment]:
    settings = get_settings()
    sem = asyncio.Semaphore(concurrency or settings.batch_concurrency)

    async def _limited(domain: str) -> DomainEnrichment:
        async with sem:
            return await enrich_domain(domain)

    return list(await asyncio.gather(*[_limited(d) for d in domains]))
