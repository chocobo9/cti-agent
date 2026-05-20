from __future__ import annotations

import asyncio
import ipaddress
from datetime import datetime
from typing import Any

import dns.asyncresolver
import dns.resolver

from cti_agent.enrichment.config import get_settings
from cti_agent.enrichment.models import DnsQueryResult, PassiveDNSRecord
from cti_agent.enrichment.utils import create_http_client, retry_async

OTX_BASE_URL = "https://otx.alienvault.com/api/v1/indicators/domain"
RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA")


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


@retry_async()
async def query_passive_dns(domain: str) -> list[PassiveDNSRecord]:
    settings = get_settings()
    if not settings.otx_api_key:
        return []
    async with create_http_client() as client:
        resp = await client.get(
            f"{OTX_BASE_URL}/{domain}/passive_dns",
            headers={"X-OTX-API-KEY": settings.otx_api_key},
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    records: list[PassiveDNSRecord] = []
    seen_ips: set[str] = set()
    for entry in data.get("passive_dns", []):
        ip = entry.get("address", "").strip()
        if not ip or ip in seen_ips:
            continue
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        seen_ips.add(ip)
        records.append(
            PassiveDNSRecord(
                ip=ip,
                first_seen=_parse_datetime(entry.get("first")),
                last_seen=_parse_datetime(entry.get("last")),
            )
        )
    return records


async def query_dns_records(domain: str) -> DnsQueryResult:
    settings = get_settings()
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = [settings.dns_resolver]
    resolver.lifetime = settings.http_timeout

    current_ips: list[str] = []
    found_types: list[str] = []
    has_mx = False
    has_spf = False
    has_dmarc = False

    async def _query(rtype: str) -> tuple[str, list[str]]:
        try:
            answer = await resolver.resolve(domain, rtype)
            return rtype, [rdata.to_text() for rdata in answer]
        except Exception:
            return rtype, []

    results = await asyncio.gather(*[_query(rt) for rt in RECORD_TYPES])
    for rtype, rdata_list in results:
        if rdata_list:
            found_types.append(rtype)
        if rtype in ("A", "AAAA"):
            current_ips.extend(rdata_list)
        elif rtype == "MX" and rdata_list:
            has_mx = True
        elif rtype == "TXT":
            for txt in rdata_list:
                if "v=spf1" in txt.lower():
                    has_spf = True
    try:
        dmarc_answer = await resolver.resolve(f"_dmarc.{domain}", "TXT")
        for rdata in dmarc_answer:
            if "v=dmarc1" in rdata.to_text().lower():
                has_dmarc = True
                break
    except Exception:
        pass

    return DnsQueryResult(
        current_ips=current_ips,
        dns_record_types=sorted(found_types),
        has_mx=has_mx,
        has_spf=has_spf,
        has_dmarc=has_dmarc,
    )
