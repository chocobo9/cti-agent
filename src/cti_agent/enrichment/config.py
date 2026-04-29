from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}
    otx_api_key: str = ""
    geoip_asn_db_path: Path = Path("./data/GeoLite2-ASN.mmdb")
    geoip_city_db_path: Path = Path("./data/GeoLite2-City.mmdb")
    http_timeout: float = 15.0
    max_retries: int = 3
    retry_base_delay: float = 1.0
    batch_concurrency: int = 10
    dns_resolver: str = "8.8.8.8"
    user_agent: str = "CTI-Agent-Enrichment/0.1"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
