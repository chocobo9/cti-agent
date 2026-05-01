from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping

from pydantic_settings import BaseSettings

ALL_SOURCES: frozenset[str] = frozenset({"crtsh", "jarm", "favicon", "pdns", "rdap", "geoip"})

SOURCE_FIELDS: Mapping[str, tuple[str, ...]] = {
    "crtsh": ("certificates",),
    "jarm": ("jarm_hash",),
    "favicon": ("favicon_hash",),
    "pdns": ("passive_dns", "current_ips", "dns_record_types", "has_mx", "has_spf", "has_dmarc"),
    "rdap": ("creation_date", "expiration_date", "registrar"),
    "geoip": ("geoip",),
}

SOURCE_ERROR_KEYS: Mapping[str, str] = {
    "crtsh": "ct_logs",
    "jarm": "jarm",
    "favicon": "favicon",
    "pdns": "passive_dns",
    "rdap": "rdap",
    "geoip": "geoip",
}

SOURCE_LABELS: Mapping[str, str] = {
    "crtsh": "crt.sh",
    "jarm": "JARM",
    "favicon": "Favicon",
    "pdns": "pDNS",
    "rdap": "RDAP",
    "geoip": "GeoIP",
}


class Settings(BaseSettings):
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}
    otx_api_key: str = ""
    geoip_asn_db_path: Path = Path("./data/GeoLite2-ASN.mmdb")
    geoip_city_db_path: Path = Path("./data/GeoLite2-City.mmdb")
    http_timeout: float = 30.0
    max_retries: int = 3
    retry_base_delay: float = 2.0
    batch_concurrency: int = 10
    dns_resolver: str = "8.8.8.8"
    user_agent: str = "CTI-Agent-Enrichment/0.1"
    crtsh_rate_limit: float = 1.0
    otx_rate_limit: float = 10.0
    rdap_rate_limit: float = 1.0
    jarm_concurrency_limit: int = 5
    favicon_concurrency_limit: int = 10


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
