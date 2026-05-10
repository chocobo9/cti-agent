from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Neo4jSettings(BaseSettings):
    """Neo4j connection configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("changeme")
    neo4j_database: str = "neo4j"
    neo4j_max_connection_pool_size: int = 50


@lru_cache(maxsize=1)
def get_settings() -> Neo4jSettings:
    """Return cached Neo4j settings singleton."""
    return Neo4jSettings()
