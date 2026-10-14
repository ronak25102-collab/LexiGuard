"""Rebuild saved/parsed contracts into the configured Aura instance and index vectors."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lexiguard.config import PARSED_DATA_DIR, get_settings
from lexiguard.evaluation.focused_ablation import GoogleCalls, write_json
from lexiguard.evaluation.live_ablation import CachedGoogleEmbeddings
from lexiguard.graph.builder import GraphBuilder
from lexiguard.graph.neo4j_client import Neo4jClient
from lexiguard.graph.schema import ContractData
from lexiguard.ingestion.source_sections import enrich_from_source
from lexiguard.ingestion.vector_store import add_contract_to_vectorstore, get_vectorstore

OUT = ROOT / "evaluation_results/live_validation"
MODEL = "gemini-3.5-flash-lite"


def main():
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)
    host = urlparse(get_settings().neo4j_uri).hostname or ""
    if not host.endswith(".databases.neo4j.io"):
        raise RuntimeError("This restoration requires the configured cloud Aura instance.")
    source = ROOT / "data/extracted_contracts.json"
    records = json.loads(source.read_text("utf-8"))
    backup = OUT / "original_extracted_contracts.json"
    if not backup.exists():
        write_json(backup, records)
    saved = {c["source_file"]: ContractData.model_validate(c) for c in records}
    calls = GoogleCalls(OUT, MODEL, "gemini-embedding-001")
    embeddings = CachedGoogleEmbeddings(calls)
    prototypes, contracts = {}, []
    with Neo4jClient() as client:
        if not client.verify_connection():
            raise RuntimeError("Cloud connection failed; no restoration attempted.")
        builder = GraphBuilder(client)
        builder.create_constraints()
        for path in sorted(PARSED_DATA_DIR.glob("*.md")):
            text = path.read_text("utf-8")
            source_id = path.stem if path.with_suffix(".status").exists() else path.name
            contract = saved.get(source_id)
            checksum = hashlib.sha256(text.encode()).hexdigest()
            if contract is None:
                if checksum not in prototypes:
                    prompt = (
                        "Extract only the title, contract_type, effective_date, expiry_date, "
                        "and parties from this contract introduction. Return JSON only. "
                        "Each party must have name, role and jurisdiction (or null). "
                        "Use verbatim party names; omit facts not present. Dates may be null. "
                        "Do not extract clauses or cross-references.\n\n" + text[:5000]
                    )
                    value = calls.text(prompt)
                    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip())
                    metadata = json.loads(value)
                    metadata["source_file"] = source_id
                    prototypes[checksum] = ContractData.model_validate(metadata)
                contract = prototypes[checksum].model_copy(update={"source_file": source_id})
            enriched = enrich_from_source(contract, text)
            contracts.append(enriched)
            builder.build_contract_graph(enriched, source_text=text)
            print("GRAPH", path.name, len(enriched.clauses), flush=True)
            with patch("lexiguard.ingestion.vector_store.get_embeddings", return_value=embeddings):
                add_contract_to_vectorstore(source_id, text)
            print("VECTORS", path.name, flush=True)
            write_json(OUT / "restored_contracts.json", [c.model_dump() for c in contracts])
        with patch("lexiguard.ingestion.vector_store.get_embeddings", return_value=embeddings):
            store = get_vectorstore()
            count = store._collection.count()
        result = {"cloud_graph": client.get_graph_stats(), "vector_chunks": count,
                  "collection": store._collection.name, "contracts": len(contracts),
                  "embedding_model": "gemini-embedding-001", "dimensions": 768}
        write_json(OUT / "restoration_summary.json", result)
        # Retain full source sections locally so a later cloud rebuild is reproducible.
        write_json(source, [c.model_dump() for c in contracts])
        print("COMPLETE", json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
