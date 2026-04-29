from __future__ import annotations

from typing import Any

from cti_agent.enrichment.config import get_settings
from cti_agent.enrichment.models import GeoIPInfo

_asn_reader: Any = None
_city_reader: Any = None


def _get_readers() -> tuple[Any, Any]:
    global _asn_reader, _city_reader
    if _asn_reader is not None and _city_reader is not None:
        return _asn_reader, _city_reader
    try:
        import geoip2.database

        settings = get_settings()
        if settings.geoip_asn_db_path.exists():
            _asn_reader = geoip2.database.Reader(str(settings.geoip_asn_db_path))
        if settings.geoip_city_db_path.exists():
            _city_reader = geoip2.database.Reader(str(settings.geoip_city_db_path))
    except ImportError:
        pass
    return _asn_reader, _city_reader


def lookup_geoip(ip: str) -> GeoIPInfo:
    asn_reader, city_reader = _get_readers()
    asn_number: int | None = None
    asn_name: str | None = None
    country: str | None = None
    city: str | None = None
    if asn_reader is not None:
        try:
            asn_resp = asn_reader.asn(ip)
            asn_number = asn_resp.autonomous_system_number
            asn_name = asn_resp.autonomous_system_organization
        except Exception:
            pass
    if city_reader is not None:
        try:
            city_resp = city_reader.city(ip)
            country = city_resp.country.iso_code
            city = city_resp.city.name
        except Exception:
            pass
    return GeoIPInfo(ip=ip, asn_number=asn_number, asn_name=asn_name, country=country, city=city)


def lookup_geoip_batch(ips: list[str]) -> list[GeoIPInfo]:
    seen: set[str] = set()
    results: list[GeoIPInfo] = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            results.append(lookup_geoip(ip))
    return results
