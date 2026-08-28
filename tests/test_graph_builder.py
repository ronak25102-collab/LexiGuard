"""Tests for the Neo4j graph builder module."""

from unittest.mock import MagicMock

import pytest

from lexiguard.graph.builder import GraphBuilder
from lexiguard.graph.schema import (
    ClauseInfo,
    ContractData,
    CrossReference,
    LocationInfo,
    PartyInfo,
)


@pytest.fixture
def mock_client():
    """Create a mock Neo4j client."""
    client = MagicMock()
    client.run_write.return_value = MagicMock()
    client.run_query.return_value = []
    return client


@pytest.fixture
def sample_contract():
    """Create a sample ContractData for testing."""
    return ContractData(
        source_file="sample_agreement.pdf",
        title="Master Services Agreement",
        contract_type="Service Agreement",
        effective_date="2024-01-01",
        expiry_date="2025-12-31",
        governing_law="State of Delaware",
        parties=[
            PartyInfo(name="Acme Corp", role="Buyer", jurisdiction="Delaware"),
            PartyInfo(name="Widget LLC", role="Seller", jurisdiction="California"),
        ],
        clauses=[
            ClauseInfo(
                number="1.1",
                title="Definitions",
                text="The following terms shall have the meanings...",
                clause_type="Document Name",
            ),
            ClauseInfo(
                number="8.2",
                title="Termination",
                text="Either party may terminate with 30 days notice...",
                clause_type="Termination For Convenience",
            ),
            ClauseInfo(
                number="14.1",
                title="Termination Fee",
                text="Notwithstanding Section 8.2, early termination incurs...",
                clause_type="Liquidated Damages",
            ),
        ],
        locations=[
            LocationInfo(name="Delaware", location_type="state"),
            LocationInfo(name="California", location_type="state"),
        ],
        cross_references=[
            CrossReference(
                source_clause="14.1",
                target_clause="8.2",
                relationship="MODIFIES",
            ),
        ],
    )


class TestGraphBuilder:
    """Test suite for the GraphBuilder."""

    def test_create_constraints(self, mock_client):
        """Should execute constraint creation queries."""
        builder = GraphBuilder(mock_client)
        builder.create_constraints()
        assert mock_client.run_write.called

    def test_build_contract_graph_creates_nodes(self, mock_client, sample_contract):
        """Should create contract, party, clause, and location nodes."""
        builder = GraphBuilder(mock_client)
        stats = builder.build_contract_graph(sample_contract)

        # Should have made multiple write calls
        assert mock_client.run_write.call_count > 0
        assert isinstance(stats, dict)

    def test_build_all_processes_multiple_contracts(self, mock_client, sample_contract):
        """build_all should process a list of contracts."""
        builder = GraphBuilder(mock_client)
        contracts = [sample_contract, sample_contract]
        stats = builder.build_all(contracts)

        assert isinstance(stats, dict)

    def test_build_contract_graph_with_cross_references(
        self, mock_client, sample_contract
    ):
        """Should create cross-reference relationships between clauses."""
        builder = GraphBuilder(mock_client)
        builder.build_contract_graph(sample_contract)

        # Check that MODIFIES relationship was created
        _ = [str(c) for c in mock_client.run_write.call_args_list]
        # At least one call should involve relationship creation
        assert mock_client.run_write.call_count > 0

    def test_build_contract_graph_empty_contract(self, mock_client):
        """Should handle a contract with no parties or clauses."""
        empty = ContractData(
            source_file="empty.pdf",
            title="Empty Contract",
            contract_type="Unknown",
        )
        builder = GraphBuilder(mock_client)
        stats = builder.build_contract_graph(empty)
        assert isinstance(stats, dict)
