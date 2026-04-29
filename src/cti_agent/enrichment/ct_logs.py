from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from cti_agent.enrichment.models import CertificateInfo
from cti_agent.enrichment.utils import create_http_client, retry_async

CRT_SH_URL = "https://crt.sh/"
_CN_PATTERN = re.compile(r"CN=([^,]+)")


def _parse_issuer_cn(issuer_name: str) -> str:
    match = _CN_PATTERN.search(issuer_name)
    return match.group(1).strip() if match else issuer_name


def _parse_san_list(name_value: str) -> list[str]:
    raw = name_value.split("\n")
    seen: set[str] = set()
    result: list[str] = []
    for entry in raw:
        entry = entry.strip().lower()
        if entry and entry not in seen:
            seen.add(entry)
            result.append(entry)
    return result


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


def _entry_to_cert(entry: dict[str, Any]) -> CertificateInfo:
    return CertificateInfo(
        fingerprint=None,
        serial_number=entry.get("serial_number"),
        issuer=_parse_issuer_cn(entry.get("issuer_name", "")),
        not_before=_parse_datetime(entry.get("not_before")),
        not_after=_parse_datetime(entry.get("not_after")),
        san_list=_parse_san_list(entry.get("name_value", "")),
    )


def _dedup_key(cert: CertificateInfo) -> str:
    return f"{cert.serial_number}|{cert.issuer}"


@retry_async()
async def query_crt_sh(domain: str) -> list[CertificateInfo]:
    async with create_http_client() as client:
        resp = await client.get(CRT_SH_URL, params={"q": domain, "output": "json"})
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()

    seen_keys: set[str] = set()
    certs: list[CertificateInfo] = []
    for entry in data:
        cert = _entry_to_cert(entry)
        key = _dedup_key(cert)
        if key not in seen_keys:
            seen_keys.add(key)
            certs.append(cert)

    certs.sort(key=lambda c: c.not_before, reverse=True)
    return certs
