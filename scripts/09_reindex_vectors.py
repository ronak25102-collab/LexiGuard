"""Reindex selected parsed contracts with the currently configured embedding model."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexiguard.config import PARSED_DATA_DIR
from lexiguard.ingestion.vector_store import add_contract_to_vectorstore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source-file", action="append", help="Parsed filename; repeat to select more.")
    group.add_argument("--all", action="store_true", help="Index every parsed Markdown contract.")
    parser.add_argument("--dry-run", action="store_true", help="List source IDs without API calls.")
    args = parser.parse_args()
    available = {path.name: path for path in PARSED_DATA_DIR.glob("*.md")}
    names = sorted(available) if args.all else list(dict.fromkeys(args.source_file))
    missing = [name for name in names if name not in available]
    if missing:
        parser.error("Parsed sources not found: " + ", ".join(missing))
    for name in names:
        path = available[name]
        # Uploads use the upload ID; batch extraction uses the Markdown filename.
        source_id = path.stem if path.with_suffix(".status").exists() else path.name
        contract_id = hashlib.sha256(source_id.encode()).hexdigest()
        print(f"{'PLAN' if args.dry_run else 'INDEX'} {name} -> {contract_id}", flush=True)
        if not args.dry_run:
            add_contract_to_vectorstore(source_id, path.read_text("utf-8"))
    print(f"{'Selected' if args.dry_run else 'Indexed'} {len(names)} contracts.")


if __name__ == "__main__":
    main()
