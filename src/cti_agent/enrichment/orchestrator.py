from __future__ import annotations

import asyncio
import logging
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
from cti_agent.enrichment.rate_limit import RateLimitedSession
from cti_agent.enrichment.rdap import query_rdap

logger = logging.getLogger(__name__)


def _source_status(enrichment: DomainEnrichment) -> str:
    """Build a human-readable status string for one enrichment result."""
    parts: list[str] = []
    checks = [
        ("crt.sh", "ct_logs", bool(enrichment.certificates)),
        ("RDAP", "rdap", enrichment.creation_date is not None or enrichment.registrar is not None),
        ("JARM", "jarm", enrichment.jarm_hash is not None),
        ("pDNS", "passive_dns", bool(enrichment.passive_dns)),
        ("favicon", "favicon", enrichment.favicon_hash is not None),
        ("GeoIP", "geoip", bool(enrichment.geoip)),
    ]
    for label, error_key, has_data in checks:
        if error_key in enrichment.errors:
            parts.append(f"{label} ✗")
        elif has_data:
            parts.append(f"{label} ✓")
        else:
            parts.append(f"{label} —")
    return ", ".join(parts)


async def enrich_domain(
    domain: str,
    rate_limiter: RateLimitedSession | None = None,
) -> DomainEnrichment:
    errors: dict[str, str] = {}

    async def _crtsh() -> list[CertificateInfo]:
        if rate_limiter:
            async with rate_limiter.crtsh:
                return await query_crt_sh(domain)
        return await query_crt_sh(domain)

    async def _jarm() -> str | None:
        if rate_limiter:
            async with rate_limiter.jarm:
                return await scan_jarm(domain)
        return await scan_jarm(domain)

    async def _favicon() -> int | None:
        if rate_limiter:
            async with rate_limiter.favicon:
                return await get_favicon_hash(domain)
        return await get_favicon_hash(domain)

    async def _pdns() -> list[PassiveDNSRecord]:
        if rate_limiter:
            async with rate_limiter.otx:
                return await query_passive_dns(domain)
        return await query_passive_dns(domain)

    async def _rdap() -> RdapResult:
        if rate_limiter:
            async with rate_limiter.rdap:
                return await query_rdap(domain)
        return await query_rdap(domain)

    results = await asyncio.gather(
        _crtsh(),
        _jarm(),
        _favicon(),
        _pdns(),
        _rdap(),
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


async def enrich_batch(
    domains: list[str],
    concurrency: int | None = None,
) -> list[DomainEnrichment]:
    settings = get_settings()
    sem = asyncio.Semaphore(concurrency or settings.batch_concurrency)
    rate_limiter = RateLimitedSession(
        crtsh_rate=settings.crtsh_rate_limit,
        otx_rate=settings.otx_rate_limit,
        rdap_rate=settings.rdap_rate_limit,
        jarm_concurrency=settings.jarm_concurrency_limit,
        favicon_concurrency=settings.favicon_concurrency_limit,
    )
    total = len(domains)
    completed = 0

    async def _limited(domain: str) -> DomainEnrichment:
        nonlocal completed
        async with sem:
            result = await enrich_domain(domain, rate_limiter=rate_limiter)
        completed += 1
        logger.info(
            "[%d/%d] %s — %s",
            completed,
            total,
            domain,
            _source_status(result),
        )
        return result

    return list(
        await asyncio.gather(*[_limited(d) for d in domains])
    )
