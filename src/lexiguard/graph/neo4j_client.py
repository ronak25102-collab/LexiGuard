"""Neo4j database client wrapper for LexiGuard.

Provides a clean interface for executing Cypher queries against the
Neo4j knowledge graph, with connection management and error handling.
"""

import logging
from typing import Any

from neo4j import GraphDatabase, ResultSummary
from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Wrapper around neo4j.GraphDatabase.driver with connection management."""

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        """Initialize the Neo4j client.

        If no arguments are provided, loads connection details from settings.
        """
        from lexiguard.config import get_settings

        settings = get_settings()
        self._uri = uri or settings.neo4j_uri
        self._username = username or settings.neo4j_username
        self._password = password or settings.neo4j_password
        self._driver = None

    def _ensure_driver(self) -> None:
        """Lazily initialize the driver on first use."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password),
            )
            logger.info(f"Initialized Neo4j driver for {self._uri}")

    def __enter__(self):
        self._ensure_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def driver(self):
        """Access the underlying driver (lazy init)."""
        self._ensure_driver()
        return self._driver

    def verify_connection(self) -> bool:
        """Test connectivity to the Neo4j database."""
        try:
            self._ensure_driver()
            self._driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j database.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False

    def run_query(
        self, cypher: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read query and return results as a list of dicts."""
        self._ensure_driver()
        parameters = parameters or {}
        try:
            with self._driver.session() as session:
                result = session.run(cypher, parameters)
                return [record.data() for record in result]
        except Neo4jError as e:
            logger.error(f"Query failed: {e}\nCypher: {cypher}\nParams: {parameters}")
            raise

    def run_write(
        self, cypher: str, parameters: dict[str, Any] | None = None
    ) -> ResultSummary:
        """Execute a write query and return the ResultSummary."""
        self._ensure_driver()
        parameters = parameters or {}
        try:
            with self._driver.session() as session:
                result = session.run(cypher, parameters)
                return result.consume()
        except Neo4jError as e:
            logger.error(
                f"Write query failed: {e}\nCypher: {cypher}\nParams: {parameters}"
            )
            raise

    def execute_query(
        self, cypher: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Alias for run_query — used by the API layer."""
        return self.run_query(cypher, parameters)

    def clear_graph(self) -> None:
        """Delete all nodes and relationships. Use with caution."""
        logger.warning("Clearing entire Neo4j graph...")
        self.run_write("MATCH (n) DETACH DELETE n")
        logger.info("Graph cleared.")

    def get_graph_stats(self) -> dict[str, Any]:
        """Return counts of nodes by label and relationships by type."""
        stats: dict[str, Any] = {"nodes": {}, "relationships": {}}

        node_counts = self.run_query(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count"
        )
        for record in node_counts:
            label = record.get("label")
            if label:
                stats["nodes"][label] = record["count"]

        rel_counts = self.run_query(
            "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(*) AS count"
        )
        for record in rel_counts:
            rel_type = record.get("rel_type")
            if rel_type:
                stats["relationships"][rel_type] = record["count"]

        return stats

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j driver closed.")


# --- Singleton ---

_client_instance: Neo4jClient | None = None


def get_client() -> Neo4jClient:
    """Get or create the singleton Neo4jClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = Neo4jClient()
    return _client_instance
