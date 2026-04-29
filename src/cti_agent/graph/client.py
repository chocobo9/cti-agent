from __future__ import annotations

import logging
from typing import Any

import neo4j
from neo4j import GraphDatabase

from cti_agent.graph.config import Neo4jSettings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Thin wrapper around the Neo4j Python driver.

    Manages driver lifecycle and provides convenience methods for read/write
    transactions with automatic retry on transient errors.
    """

    def __init__(self, settings: Neo4jSettings) -> None:
        self._settings = settings
        self._driver: neo4j.Driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
            max_connection_pool_size=settings.neo4j_max_connection_pool_size,
        )
        self._database = settings.neo4j_database

    def verify_connectivity(self) -> None:
        """Verify the driver can reach the Neo4j server."""
        self._driver.verify_connectivity()
        logger.info("Neo4j connectivity verified: %s", self._settings.neo4j_uri)

    def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run a read transaction and return all result records as dicts."""
        with self._driver.session(database=self._database) as session:
            return session.execute_read(
                lambda tx: tx.run(query, parameters or {}).data()
            )

    def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run a write transaction and return all result records as dicts."""
        with self._driver.session(database=self._database) as session:
            return session.execute_write(
                lambda tx: tx.run(query, parameters or {}).data()
            )

    def close(self) -> None:
        """Close the underlying driver and release all resources."""
        self._driver.close()
        logger.info("Neo4j driver closed")

    def __enter__(self) -> Neo4jClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
