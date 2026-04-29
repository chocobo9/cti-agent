from __future__ import annotations

from datetime import date, datetime
from typing import Any

from cti_agent.enrichment.models import RdapResult
from cti_agent.enrichment.utils import create_http_client, retry_async

RDAP_BASE_URL = "https://rdap.org/domain"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _extract_dates(events: list[dict[str, Any]]) -> tuple[date | None, date | None]:
    creation: date | None = None
    expiration: date | None = None
    for event in events:
        action = event.get("eventAction", "").lower()
        event_date = _parse_date(event.get("eventDate"))
        if action == "registration":
            creation = event_date
        elif action == "expiration":
            expiration = event_date
    return creation, expiration


def _extract_registrar(entities: list[dict[str, Any]]) -> str | None:
    for entity in entities:
        roles = entity.get("roles", [])
        if "registrar" in roles:
            vcard = entity.get("vcardArray")
            if isinstance(vcard, list) and len(vcard) >= 2:
                for field in vcard[1]:
                    if isinstance(field, list) and len(field) >= 4 and field[0] == "fn":
                        return str(field[3])
            handle = entity.get("handle")
            if handle:
                return str(handle)
    return None


@retry_async()
async def query_rdap(domain: str) -> RdapResult:
    async with create_http_client() as client:
        resp = await client.get(f"{RDAP_BASE_URL}/{domain}")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    creation, expiration = _extract_dates(data.get("events", []))
    registrar = _extract_registrar(data.get("entities", []))
    return RdapResult(creation_date=creation, expiration_date=expiration, registrar=registrar)
