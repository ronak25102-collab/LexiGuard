"""Verify that Aura connections retain TLS certificate and hostname validation."""

import ssl
from unittest.mock import patch

from lexiguard.graph.neo4j_client import Neo4jClient


def test_aura_driver_uses_a_verified_ssl_context():
    with patch("lexiguard.graph.neo4j_client.GraphDatabase.driver") as factory:
        client = Neo4jClient(uri="neo4j+s://example.databases.neo4j.io",
                             username="test", password="test-password")
        client._ensure_driver()
        args, options = factory.call_args
        assert args == ("neo4j://example.databases.neo4j.io",)
        assert options["ssl_context"].check_hostname
        assert options["ssl_context"].verify_mode == ssl.CERT_REQUIRED
        assert options["connection_timeout"] > 0


def test_plain_bolt_configuration_does_not_silently_change_transport():
    with patch("lexiguard.graph.neo4j_client.GraphDatabase.driver") as factory:
        client = Neo4jClient(uri="bolt://localhost:7687", username="test", password="test-password")
        client._ensure_driver()
        args, options = factory.call_args
        assert args == ("bolt://localhost:7687",)
        assert "ssl_context" not in options
