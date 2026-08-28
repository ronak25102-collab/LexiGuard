#!/usr/bin/env python3
"""Script 02: Parse PDF contracts into clean Markdown."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexiguard.config import get_settings
from lexiguard.ingestion.parser import parse_all_contracts


def main():
    settings = get_settings()
    settings.ensure_data_dirs()

    print("=" * 60)
    print("LexiGuard - Step 2: Parse Contracts (PDF → Markdown)")
    print("=" * 60)

    use_llama = bool(settings.llama_cloud_api_key)
    parser_name = "LlamaCloud" if use_llama else "pymupdf4llm (free)"
    print(f"\n  Parser: {parser_name}")

    parsed_paths = parse_all_contracts()
    print(f"\n  ✓ Parsed {len(parsed_paths)} contracts to data/parsed/")

    print("\n" + "=" * 60)
    print("Done! Markdown files ready for entity extraction.")
    print("=" * 60)


if __name__ == "__main__":
    main()
