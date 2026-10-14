"""Freeze a fresh cohort after developing evidence selection on the first live pilot."""

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from lexiguard.evaluation.focused_ablation import GoogleCalls, digest, write_json
from lexiguard.evaluation.live_ablation import CachedCompatibleCalls, CachedGoogleEmbeddings
from lexiguard.graph.builder import GraphBuilder
from lexiguard.graph.neo4j_client import Neo4jClient
from lexiguard.graph.schema import ContractData
from lexiguard.ingestion.source_sections import enrich_from_source
from lexiguard.ingestion.vector_store import add_contract_to_vectorstore, get_vectorstore

OUT = ROOT / "evaluation_results/live_guard_validation"


def main():
    if (OUT / "questions.json").exists():
        raise RuntimeError("Fresh questions are frozen; do not overwrite them.")
    selection = json.loads((OUT / "selection.json").read_text("utf-8"))
    official = json.loads((ROOT / "data/cuad_qa/CUAD_v1.json").read_text("utf-8"))
    titles = [c["title"] for c in selection["contracts"]]
    source_records = json.loads((ROOT / "data/extracted_contracts.json").read_text("utf-8"))
    records_by_file = {r["source_file"]: r for r in source_records}
    metadata_calls = CachedCompatibleCalls(OUT, "codecraft", "gpt-5.6-luna", require_json=True)
    embedding_calls = GoogleCalls(OUT, "gemini-3.5-flash-lite", "gemini-embedding-001")
    for cache in (ROOT / "evaluation_results/live_validation/cache").glob("*.json"):
        if isinstance(json.loads(cache.read_text("utf-8")), list):
            destination = embedding_calls.cache / cache.name
            if not destination.exists():
                shutil.copy2(cache, destination)
    embeddings = CachedGoogleEmbeddings(embedding_calls)
    cases, full_entries = [], []
    with Neo4jClient() as client:
        if not client.verify_connection():
            raise RuntimeError("Live Aura is required")
        builder = GraphBuilder(client)
        for title in titles:
            entry = next(c for c in official["data"] if c["title"] == title)
            full_entries.append(entry)
            text = entry["paragraphs"][0]["context"]
            source = "cuad_" + hashlib.sha256(title.encode()).hexdigest()[:16] + ".md"
            (ROOT / "data/parsed" / source).write_text(text, "utf-8")
            if source not in records_by_file:
                prompt = ("Extract only title, contract_type, effective_date, expiry_date and parties "
                          "from this source introduction. Every party must have name, role and "
                          "jurisdiction (or null). Use only verbatim party names. Omit unknown "
                          "dates. Return JSON only; do not extract clauses or references.\n\n" + text[:5000])
                value = json.loads(metadata_calls.text(prompt).strip().removeprefix("```json")
                                   .removesuffix("```").strip())
                # Unknown roles remain explicitly unspecified, not inferred obligations.
                for party in value.get("parties", []):
                    if party.get("role") is None:
                        party["role"] = "Unspecified"
                records_by_file[source] = ContractData(source_file=source, **value).model_dump()
            record = enrich_from_source(ContractData.model_validate(records_by_file[source]), text)
            records_by_file[source] = record.model_dump()
            builder.build_contract_graph(record, source_text=text)
            with patch("lexiguard.ingestion.vector_store.get_embeddings", return_value=embeddings):
                add_contract_to_vectorstore(source, text)
            write_json(ROOT / "data/extracted_contracts.json", list(records_by_file.values()))
            write_json(OUT / "corpus" / (hashlib.sha256(source.encode()).hexdigest() + ".json"), record.model_dump())
            selected = []
            for category in selection["categories"]:
                eligible = [q for q in entry["paragraphs"][0]["qas"]
                            if q["id"].split("__")[-1] == category and q["answers"]]
                if not eligible:
                    continue
                q = eligible[0]
                spans = list(dict.fromkeys(a["text"].strip() for a in q["answers"]))
                reference = "\n\n".join(spans)
                if len(reference) > 2500:
                    continue
                selected.append({"id": f"F{len(cases)+len(selected)+1:02d}",
                    "contract_id": hashlib.sha256(source.encode()).hexdigest(), "source_file": source,
                    "official_contract_title": title, "question": q["question"], "reference": reference,
                    "reference_spans": spans, "category": category, "official_cuad_id": q["id"],
                    "cohort": "fresh_guard_validation"})
                if len(selected) == 4:
                    break
            if len(selected) != 4:
                raise RuntimeError("Prespecified eligible case count failed")
            cases.extend(selected)
            print("PREPARED_FRESH_SOURCE", title, len(record.clauses), flush=True)
        snapshot = client.run_query("""MATCH (c:Contract)-[:CONTAINS_CLAUSE]->(cl:Clause)
          RETURN c.id AS contract_id, c.source_file AS source_file, cl.number AS section,
                 cl.title AS title, cl.clause_type AS clause_type, cl.text AS text
          ORDER BY contract_id, section""")
        stats = client.get_graph_stats()
    with patch("lexiguard.ingestion.vector_store.get_embeddings", return_value=embeddings):
        store = get_vectorstore()
    old_protocol = json.loads((ROOT / "evaluation_results/live_validation/protocol.json").read_text("utf-8"))
    protocol = {**old_protocol, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": len(cases), "question_source": "Original CUAD questions and unchanged annotated spans; full official source text indexed separately from answer labels",
        "primary_pairing": "faithfulness_context_precision_only",
        "sampling": selection["method"] + "; first four eligible categories in declared order, reference <=2500 chars",
        "contract_prefixes": titles, "categories_in_order": selection["categories"],
        "graph_stats": stats, "chroma_chunks": store._collection.count(),
        "questions_sha256": digest(cases), "graph_snapshot_sha256": digest(snapshot),
        "source_hashes": {str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (ROOT / 'src/lexiguard').rglob('*.py')},
        "development_history": "First live 26-case pilot revealed evidence displacement. Added semantic-versus-hybrid comparison in the CRAG relevance node, generic non-compete/exclusivity/revenue search expansion, and atomic parser prefixes. This fresh 24-case cohort was selected without inspecting system outputs.",
        "evidence_guard": "CRAG compares the same bounded semantic-only and hybrid candidates, prefers complete semantic evidence if hybrid adds no substantive fact, and checks relevance. Non-CRAG variants retain their existing paths.",
        "source_parsing": "Full original CUAD text, not a new PDF parse. Clause contents/explicit references are parsed without labels; only introduction metadata uses the generator.",
        "measurement_source": "measurement_source/: exact source files matching frozen hashes",
        "availability_amendment": "Models fixed from the start of this fresh cohort; previous Google's quota event belongs to the first live pilot."}
    for path in (ROOT / "src/lexiguard").rglob("*.py"):
        target = OUT / "measurement_source" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    write_json(OUT / "questions.json", cases)
    write_json(OUT / "graph_snapshot.json", snapshot)
    write_json(OUT / "official_entries.json", {"data": full_entries})
    write_json(OUT / "protocol.json", protocol)
    print("FROZEN_FRESH", len(cases), "cases;", store._collection.count(), "chunks", flush=True)


if __name__ == "__main__":
    main()
