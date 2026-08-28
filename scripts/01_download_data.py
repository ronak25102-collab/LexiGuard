#!/usr/bin/env python3
"""Script 01: Download CUAD contracts from HuggingFace."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexiguard.config import get_settings
from lexiguard.ingestion.downloader import download_cuad_contracts, download_cuad_qa


def main():
    settings = get_settings()
    settings.ensure_data_dirs()

    print("=" * 60)
    print("LexiGuard - Step 1: Download CUAD Dataset")
    print("=" * 60)

    # Download contracts
    print("\n[1/2] Downloading CUAD contracts...")
    pdf_paths = download_cuad_contracts(num_contracts=10)
    print(f"  ✓ Downloaded {len(pdf_paths)} contracts")

    # Download QA data for evaluation
    print("\n[2/2] Downloading CUAD QA dataset...")
    download_cuad_qa()
    print("  ✓ QA dataset ready")

    print("\n" + "=" * 60)
    print("Done! Contracts saved to data/raw/")
    print("=" * 60)


if __name__ == "__main__":
    main()
