#!/usr/bin/env python3
"""Script 04: Build Neo4j knowledge graph from extracted entities."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexiguard.config import DATA_DIR, get_settings
from lexiguard.graph.builder import GraphBuilder
from lexiguard.graph.neo4j_client import Neo4jClient
from lexiguard.graph.schema import ContractData


def main():
    settings = get_settings()

    print("=" * 60)
    print("LexiGuard - Step 4: Build Neo4j Knowledge Graph")
    print("=" * 60)

    # Load extracted contracts
    extracted_path = DATA_DIR / "extracted_contracts.json"
    if not extracted_path.exists():
        print("  ✗ No extracted data found. Run script 03 first.")
        sys.exit(1)

    with open(extracted_path, encoding="utf-8") as f:
        raw_contracts = json.load(f)

    contracts = [ContractData.model_validate(c) for c in raw_contracts]
    print(f"\n  Loaded {len(contracts)} contracts from {extracted_path.name}")

    # Connect to Neo4j and build graph
    print(f"\n  Connecting to Neo4j: {settings.neo4j_uri}")
    with Neo4jClient() as client:
        if not client.verify_connection():
            print("  ✗ Failed to connect to Neo4j. Check your .env settings.")
            sys.exit(1)
        print("  ✓ Connected to Neo4j")

        builder = GraphBuilder(client)

        # Create constraints
        print("\n  Creating uniqueness constraints...")
        builder.create_constraints()
        print("  ✓ Constraints created")

        # Build the graph
        print("\n  Building knowledge graph...")
        stats = builder.build_all(contracts)

        print("\n  ✓ Graph built successfully!")
        print("\n  Graph Statistics:")
        for key, value in stats.items():
            print(f"    {key}: {value}")

    print("\n" + "=" * 60)
    print("Done! Knowledge graph is ready. Open Neo4j Aura to visualize.")
    print("=" * 60)


if __name__ == "__main__":
    main()
