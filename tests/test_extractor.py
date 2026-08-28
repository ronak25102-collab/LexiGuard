"""Tests for the entity extractor module."""


from lexiguard.graph.schema import ClauseInfo, ContractData, PartyInfo


class TestExtractor:
    """Test suite for the LLM entity extractor."""

    def test_contract_data_model_validation(self):
        """ContractData should validate correctly with required fields."""
        data = ContractData(
            source_file="test.pdf",
            title="Master Services Agreement",
            contract_type="Service Agreement",
            parties=[
                PartyInfo(name="Acme Corp", role="Buyer"),
                PartyInfo(name="Widget Inc", role="Seller"),
            ],
            clauses=[
                ClauseInfo(
                    number="1.1",
                    title="Definitions",
                    text="The following terms...",
                    clause_type="Document Name",
                ),
            ],
        )
        assert data.title == "Master Services Agreement"
        assert len(data.parties) == 2
        assert len(data.clauses) == 1

    def test_contract_data_optional_fields(self):
        """Optional fields should default to None/empty."""
        data = ContractData(
            source_file="test.pdf",
            title="NDA",
            contract_type="Non-Disclosure Agreement",
        )
        assert data.effective_date is None
        assert data.expiry_date is None
        assert data.governing_law is None
        assert data.parties == []
        assert data.clauses == []
        assert data.cross_references == []

    def test_contract_data_serialization(self):
        """ContractData should serialize to dict and JSON correctly."""
        data = ContractData(
            source_file="test.pdf",
            title="License Agreement",
            contract_type="License",
            governing_law="Delaware",
            parties=[PartyInfo(name="LicCo", role="Licensor", jurisdiction="DE")],
        )
        d = data.model_dump()
        assert d["governing_law"] == "Delaware"
        assert d["parties"][0]["jurisdiction"] == "DE"

        json_str = data.model_dump_json()
        assert "License Agreement" in json_str

    def test_party_info_without_jurisdiction(self):
        """PartyInfo should work without jurisdiction."""
        party = PartyInfo(name="SomeCorp", role="Vendor")
        assert party.jurisdiction is None
