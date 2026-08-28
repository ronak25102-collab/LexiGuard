#!/usr/bin/env python3
"""Script 03: Extract structured entities from parsed contracts using LLM."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexiguard.config import DATA_DIR, get_settings
from lexiguard.ingestion.extractor import extract_all_contracts


def main():
    settings = get_settings()
    settings.ensure_data_dirs()

    print("=" * 60)
    print("LexiGuard - Step 3: Extract Legal Entities (LLM)")
    print("=" * 60)
    print(f"\n  LLM Provider: {settings.llm_provider.value}")
    print(f"  Model: {settings.active_model}")

    contracts = extract_all_contracts()

    # Save extracted data as JSON for inspection
    output_path = DATA_DIR / "extracted_contracts.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            [c.model_dump() for c in contracts],
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n  ✓ Extracted entities from {len(contracts)} contracts")
    print(f"  ✓ Saved to {output_path}")

    # Summary
    total_parties = sum(len(c.parties) for c in contracts)
    total_clauses = sum(len(c.clauses) for c in contracts)
    total_xrefs = sum(len(c.cross_references) for c in contracts)
    print("\n  Summary:")
    print(f"    Parties:          {total_parties}")
    print(f"    Clauses:          {total_clauses}")
    print(f"    Cross-References: {total_xrefs}")

    print("\n" + "=" * 60)
    print("Done! Entities ready for graph construction.")
    print("=" * 60)


if __name__ == "__main__":
    main()
