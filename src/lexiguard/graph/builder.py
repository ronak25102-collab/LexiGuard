import hashlib
import logging
from typing import Any

from lexiguard.graph.neo4j_client import Neo4jClient, get_client
from lexiguard.graph.schema import ContractData

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class GraphBuilder:
    """Knowledge graph builder that takes extracted ContractData and creates Neo4j nodes/relationships."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    def create_constraints(self) -> None:
        """Create uniqueness constraints on nodes."""
        logger.info("Creating uniqueness constraints...")
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Contract) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Party) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (cl:Clause) REQUIRE cl.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
        ]
        for query in constraints:
            self.client.run_write(query)
        logger.info("Constraints created successfully.")

    def _generate_contract_id(self, source_file: str) -> str:
        return hashlib.sha256(source_file.encode("utf-8")).hexdigest()

    def _generate_clause_id(self, contract_id: str, clause_number: str) -> str:
        return f"{contract_id}_{clause_number}"

    def build_contract_graph(self, contract: ContractData, source_text: str | None = None) -> dict[str, Any]:
        """Takes a single ContractData, creates all nodes and relationships."""
        logger.info(f"Building graph for contract: {contract.title} ({contract.source_file})")

        from lexiguard.config import PARSED_DATA_DIR
        from lexiguard.ingestion.source_sections import enrich_from_source

        if source_text is None:
            for name in (contract.source_file, contract.source_file + ".md"):
                path = (PARSED_DATA_DIR / name).resolve()
                if path.is_relative_to(PARSED_DATA_DIR.resolve()) and path.is_file():
                    source_text = path.read_text("utf-8")
                    break
        if source_text:
            contract = enrich_from_source(contract, source_text)
            # Reconcile only obsolete recital labels produced by earlier source parsing.
            # Main source sections and unrelated contracts are unaffected.
            self.client.run_write("""
                MATCH (c:Contract {id: $contract_id})-[:CONTAINS_CLAUSE]->(cl:Clause)
                WHERE cl.number STARTS WITH 'Recitals.' AND NOT cl.number IN $numbers
                DETACH DELETE cl
                """, {"contract_id": self._generate_contract_id(contract.source_file),
                      "numbers": [cl.number for cl in contract.clauses]})

        self._create_contract_node(contract)
        self._create_party_nodes(contract)
        self._create_clause_nodes(contract)
        self._create_location_nodes(contract)
        self._create_cross_references(contract)

        # Return basic stats for this contract addition
        return {
            "parties_added": len(contract.parties),
            "clauses_added": len(contract.clauses),
            "locations_added": len(contract.locations),
            "cross_references_added": len(contract.cross_references)
        }

    def build_all(self, contracts: list[ContractData]) -> dict[str, Any]:
        """Process all contracts, return aggregate stats."""
        total_stats = {
            "contracts_processed": 0,
            "parties_added": 0,
            "clauses_added": 0,
            "locations_added": 0,
            "cross_references_added": 0
        }
        for contract in contracts:
            stats = self.build_contract_graph(contract)
            total_stats["contracts_processed"] += 1
            total_stats["parties_added"] += stats["parties_added"]
            total_stats["clauses_added"] += stats["clauses_added"]
            total_stats["locations_added"] += stats["locations_added"]
            total_stats["cross_references_added"] += stats["cross_references_added"]

        logger.info(f"Processed {len(contracts)} contracts.")
        return total_stats

    def _create_contract_node(self, contract: ContractData) -> None:
        contract_id = self._generate_contract_id(contract.source_file)
        query = """
        MERGE (c:Contract {id: $id})
        ON CREATE SET c.title = $title,
                      c.source_file = $source_file,
                      c.contract_type = $contract_type,
                      c.type = $contract_type,
                      c.effective_date = $effective_date,
                      c.expiry_date = $expiry_date,
                      c.governing_law = $governing_law
        ON MATCH SET c.title = $title,
                     c.contract_type = $contract_type,
                     c.type = $contract_type,
                     c.effective_date = $effective_date,
                     c.expiry_date = $expiry_date,
                     c.governing_law = $governing_law
        """
        params = {
            "id": contract_id,
            "title": contract.title,
            "source_file": contract.source_file,
            "contract_type": contract.contract_type,
            "effective_date": contract.effective_date,
            "expiry_date": contract.expiry_date,
            "governing_law": contract.governing_law
        }
        self.client.run_write(query, params)

    def _create_party_nodes(self, contract: ContractData) -> None:
        contract_id = self._generate_contract_id(contract.source_file)
        for party in contract.parties:
            query = """
            MATCH (c:Contract {id: $contract_id})
            MERGE (p:Party {name: $name})
            ON CREATE SET p.jurisdiction = $jurisdiction
            MERGE (c)-[r:HAS_PARTY {role: $role}]->(p)
            """
            params = {
                "contract_id": contract_id,
                "name": party.name,
                "jurisdiction": party.jurisdiction,
                "role": party.role
            }
            self.client.run_write(query, params)

    def _create_clause_nodes(self, contract: ContractData) -> None:
        contract_id = self._generate_contract_id(contract.source_file)
        if not contract.clauses:
            return
        query = """
        UNWIND $clauses AS item
        MATCH (c:Contract {id: $contract_id})
        MERGE (cl:Clause {id: item.id})
        SET cl.number = item.number, cl.title = item.title,
            cl.text = item.text, cl.clause_type = item.clause_type
        MERGE (c)-[:CONTAINS_CLAUSE]->(cl)
        """
        self.client.run_write(query, {"contract_id": contract_id, "clauses": [
            {**clause.model_dump(), "id": self._generate_clause_id(contract_id, clause.number)}
            for clause in contract.clauses]})

    def _create_location_nodes(self, contract: ContractData) -> None:
        contract_id = self._generate_contract_id(contract.source_file)
        for location in contract.locations:
            query = """
            MATCH (c:Contract {id: $contract_id})
            MERGE (l:Location {name: $name})
            ON CREATE SET l.location_type = $location_type
            MERGE (c)-[:GOVERNED_BY]->(l)
            """
            params = {
                "contract_id": contract_id,
                "name": location.name,
                "location_type": location.location_type
            }
            self.client.run_write(query, params)

    def _create_cross_references(self, contract: ContractData) -> None:
        contract_id = self._generate_contract_id(contract.source_file)
        grouped = {}
        for xref in contract.cross_references:
            source_id = self._generate_clause_id(contract_id, xref.source_clause)
            target_id = self._generate_clause_id(contract_id, xref.target_clause)

            rel_type = xref.relationship.upper()
            allowed_types = {"REFERENCES", "MODIFIES", "SUPERSEDES", "EXCLUDES"}
            if rel_type not in allowed_types:
                rel_type = "REFERENCES"

            grouped.setdefault(rel_type, []).append({"source_id": source_id, "target_id": target_id})
        for rel_type, rows in grouped.items():
            query = f"""
            UNWIND $edges AS item
            MATCH (source:Clause {{id: item.source_id}})
            MATCH (target:Clause {{id: item.target_id}})
            MERGE (source)-[r:{rel_type}]->(target)
            """
            self.client.run_write(query, {"edges": rows})

if __name__ == '__main__':
    from lexiguard.graph.schema import ClauseInfo, CrossReference, LocationInfo, PartyInfo

    # Sample ContractData
    sample_contract = ContractData(
        source_file="sample_nda.pdf",
        title="Mutual Non-Disclosure Agreement",
        contract_type="NDA",
        effective_date="2023-01-01",
        governing_law="California",
        parties=[
            PartyInfo(name="Acme Corp", role="Disclosing Party", jurisdiction="Delaware"),
            PartyInfo(name="Globex Inc", role="Receiving Party", jurisdiction="California")
        ],
        clauses=[
            ClauseInfo(number="1", title="Definition of Confidential Information", text="Confidential info means...", clause_type="Document Name"),
            ClauseInfo(number="2", title="Obligations", text="Receiving party shall not disclose...", clause_type="Non-Compete")
        ],
        locations=[
            LocationInfo(name="California", location_type="state")
        ],
        cross_references=[
            CrossReference(source_clause="2", target_clause="1", relationship="REFERENCES")
        ]
    )

    client = get_client()
    try:
        if client.verify_connection():
            builder = GraphBuilder(client)
            builder.create_constraints()
            builder.build_contract_graph(sample_contract)

            stats = client.get_graph_stats()
            print("Graph Stats:", stats)
    finally:
        client.close()
