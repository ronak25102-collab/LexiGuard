"""Run a frozen, paired LangGraph ablation against cloud Aura and persistent Chroma."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import logging
import math
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lexiguard.agent.graph import build_graph
from lexiguard.config import get_settings
from lexiguard.evaluation.focused_ablation import GoogleCalls, digest, write_json
from lexiguard.evaluation.live_ablation import CachedGoogleEmbeddings, PinnedGoogleChat, CachedCompatibleCalls
from lexiguard.graph.neo4j_client import Neo4jClient
from lexiguard.ingestion.vector_store import get_vectorstore

OUT = ROOT / "evaluation_results/live_validation"
MODEL = "gemini-3.5-flash-lite"
GENERATOR_PROVIDER = "codecraft"
GENERATOR_MODEL = "gpt-5.6-luna"
JUDGE_PROVIDER = "nvidia"
JUDGE_MODEL = "nvidia/nemotron-3-super-120b-a12b"
VARIANTS = ("vector", "hybrid_no_links", "hybrid", "hybrid_crag")
PREFIXES = ("CreditcardscomInc", "EbixInc", "SouthernStarEnergyInc", "SteelVaultCorp",
            "UnionDentalHoldingsInc", "UsioInc")
CATEGORIES = ("Governing Law", "Audit Rights", "Anti-Assignment", "Renewal Term",
              "Termination For Convenience", "Cap On Liability", "License Grant",
              "Exclusivity", "Non-Compete", "No-Solicit Of Customers",
              "Revenue/Profit Sharing", "Minimum Commitment", "Warranty Duration")


class LoggedCalls(GoogleCalls):
    def text(self, prompt, model=None):
        value = super().text(prompt, model)
        write_json(self.cache / (digest([model or self.model, prompt, 0, 8192]) + ".json"),
                   {"model": model or self.model, "prompt": prompt, "text": value})
        return value


class TrackedCloudClient(Neo4jClient):
    def __init__(self):
        super().__init__()
        self.queries = []

    def run_query(self, cypher, parameters=None):
        started = time.perf_counter()
        rows = super().run_query(cypher, parameters)
        self.queries.append({"cypher": cypher, "parameters": parameters or {},
                             "rows": rows, "seconds": time.perf_counter() - started})
        return rows


def _source_id(record):
    return hashlib.sha256(record["source_file"].encode()).hexdigest()


def freeze():
    settings = get_settings()
    if not (urlparse(settings.neo4j_uri).hostname or "").endswith(".databases.neo4j.io"):
        raise RuntimeError("Live Aura is required.")
    if (OUT / "questions.json").exists():
        raise RuntimeError("Questions are already frozen; preserve them rather than resampling.")
    contracts = json.loads((ROOT / "data/extracted_contracts.json").read_text("utf-8"))
    official = json.loads((ROOT / "data/cuad_qa/CUAD_v1.json").read_text("utf-8"))
    cases = []
    for prefix in PREFIXES:
        record = next(c for c in contracts if c["source_file"].startswith(prefix))
        qa_contract = next(c for c in official["data"] if c["title"].startswith(prefix))
        qas = qa_contract["paragraphs"][0]["qas"]
        selected = []
        for category in CATEGORIES:
            matches = [q for q in qas if q["id"].split("__")[-1] == category and q["answers"]]
            if not matches:
                continue
            question = matches[0]
            answers = list(dict.fromkeys(a["text"].strip() for a in question["answers"]))
            reference = "\n\n".join(answers)
            # Prespecified length filter keeps the reference feasible within the evidence budget.
            if len(reference) > 2500:
                continue
            selected.append({"id": f"L{len(cases) + len(selected) + 1:02d}",
                "contract_id": _source_id(record), "source_file": record["source_file"],
                "question": question["question"], "reference": reference,
                "reference_spans": answers, "category": category,
                "official_cuad_id": question["id"], "cohort": "prospective_CUAD"})
            if len(selected) == 5:
                break
        cases.extend(selected)
    if len(cases) < 20:
        raise RuntimeError(f"Only {len(cases)} cases matched the prespecified sample.")
    calls = LoggedCalls(OUT, MODEL, "gemini-embedding-001")
    with patch("lexiguard.ingestion.vector_store.get_embeddings",
               return_value=CachedGoogleEmbeddings(calls)):
        store = get_vectorstore()
    with Neo4jClient() as client:
        if not client.verify_connection():
            raise RuntimeError("Cloud unavailable; no offline substitution is permitted.")
        snapshot = client.run_query("""MATCH (c:Contract)-[:CONTAINS_CLAUSE]->(cl:Clause)
            RETURN c.id AS contract_id, c.source_file AS source_file, cl.number AS section,
                   cl.title AS title, cl.clause_type AS clause_type, cl.text AS text
            ORDER BY contract_id, section""")
        stats = client.get_graph_stats()
    for c in contracts:
        write_json(OUT / "corpus" / (_source_id(c) + ".json"), c)
    write_json(OUT / "questions.json", cases)
    write_json(OUT / "graph_snapshot.json", snapshot)
    write_json(OUT / "protocol.json", {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(), "cases": len(cases),
        "generator": MODEL, "judge": MODEL, "embedding": "gemini-embedding-001",
        "embedding_dimensions": 768, "variants": VARIANTS,
        "graph_transport": "live Aura Bolt/TLS with hostname and certificate verification",
        "graph_stats": stats, "chroma_collection": store._collection.name,
        "chroma_chunks": store._collection.count(), "context_chars": 4500, "max_contexts": 3,
        "max_rewrites": 2, "sampling": "up to five positive categories per contract in declared order; reference <=2500 characters",
        "question_source": "Original CUAD_v1 questions and annotated answer spans; no synthetic test cases",
        "questions_sha256": digest(cases), "graph_snapshot_sha256": digest(snapshot),
        "categories_in_order": CATEGORIES, "contract_prefixes": PREFIXES,
        "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (ROOT / "src/lexiguard").rglob("*.py")},
        "versions": {n: importlib.metadata.version(n) for n in ["ragas", "neo4j", "chromadb", "google-genai"]},
        "limitations": ["positive-answer curated sample, not full CUAD", "one run per arm",
                        "same generator/judge", "fixed provider sampling defaults; temperature zero is not deterministic",
                        "cached model/embedding calls allowed; graph reads are never replayed"]})
    print("FROZEN", len(cases), "official CUAD cases across", len(PREFIXES), "contracts", flush=True)


def development_cases():
    records = json.loads((ROOT / "data/extracted_contracts.json").read_text("utf-8"))
    old = json.loads((ROOT / "evaluation_results/focused_ablation/questions.json").read_text("utf-8"))
    other = json.loads((ROOT / "evaluation_results/accuracy_improvement/questions.json").read_text("utf-8"))
    mapping = {"msa_demo": "# MASTER SOFTWARE", "ediets": "EdietsComInc", "tube": "TubeMediaCorp",
               "cybergy": "CybergyHoldingsInc", "linkplus": "LinkPlusCorp"}
    selected = [q for q in old + other if q["id"] in {"Q01", "Q03", "Q04", "Q10", "H04", "H05", "H06"}]
    return [{**q, "contract_id": _source_id(next(c for c in records
                                                if c["source_file"].startswith(mapping[q["contract"]])))}
            for q in selected]


def generate(development=False):
    cases = development_cases() if development else json.loads((OUT / "questions.json").read_text("utf-8"))
    path = OUT / ("development_answers.json" if development else "answers.json")
    rows = json.loads(path.read_text("utf-8")) if path.exists() else []
    complete = {(r["case_id"], r["variant"]) for r in rows if "error" not in r}
    calls = CachedCompatibleCalls(OUT, GENERATOR_PROVIDER, GENERATOR_MODEL)
    embedding_calls = LoggedCalls(OUT, MODEL, "gemini-embedding-001")
    chat = PinnedGoogleChat(calls)
    local = threading.local()
    get_settings().agent_max_retries = 2
    with patch("lexiguard.ingestion.vector_store.get_embeddings",
               return_value=CachedGoogleEmbeddings(embedding_calls)):
        store = get_vectorstore()

    def no_lexical_fallback(*args, **kwargs):
        raise RuntimeError("The live benchmark forbids offline/lexical fallback.")

    def answer(case, variant):
        started = time.perf_counter()
        client = TrackedCloudClient()
        local.client = client
        state = {"question": case["question"], "retrieval_question": case["question"],
                 "contract_filter": case["contract_id"], "retry_count": 0, "graph_context": [],
                 "documents": [], "generation": "", "relevance_score": "", "cypher_query": ""}
        trace = []
        try:
            for update in build_graph(variant).stream(state, stream_mode="updates"):
                for node, values in update.items():
                    state.update(values)
                    trace.append({"node": node, "update": values})
                    if values.get("retrieval_errors"):
                        raise RuntimeError("Live retrieval failed: " + ",".join(values["retrieval_errors"]))
            return {"case_id": case["id"], "variant": variant, "question": case["question"],
                    "contract_id": case["contract_id"], "answer": state["generation"],
                    "contexts": state["documents"], "trace": trace, "cloud_queries": client.queries,
                    "rewrites": state["retry_count"], "relevance": state["relevance_score"],
                    "seconds": time.perf_counter() - started,
                    "generator_provider": GENERATOR_PROVIDER, "generator_model": GENERATOR_MODEL}
        finally:
            client.close()

    variants = ("hybrid_crag",) if development else VARIANTS
    with patch("lexiguard.agent.nodes.get_llm", return_value=chat), \
         patch("lexiguard.agent.nodes.get_vectorstore", return_value=store), \
         patch("lexiguard.agent.nodes._get_neo4j_client", side_effect=lambda: local.client), \
         patch("lexiguard.agent.nodes._local_source_candidates", side_effect=no_lexical_fallback):
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {pool.submit(answer, case, variant): (case, variant)
                    for case in cases for variant in variants if (case["id"], variant) not in complete}
            for future in as_completed(jobs):
                case, variant = jobs[future]
                try:
                    row = future.result()
                    print("ANSWERED", case["id"], variant, len(row["cloud_queries"]), "live queries", flush=True)
                except Exception as error:
                    row = {"case_id": case["id"], "variant": variant,
                           "error": str(error).replace(calls.key, "[redacted]")[:500]}
                    print("FAILED", case["id"], variant, type(error).__name__, flush=True)
                rows = [r for r in rows if (r["case_id"], r["variant"]) != (case["id"], variant)] + [row]
                write_json(path, rows)


async def score():
    import lexiguard.evaluation.evaluate  # noqa: F401
    from langchain_core.outputs import Generation, LLMResult
    from ragas import SingleTurnSample
    from ragas.llms import BaseRagasLLM
    from ragas.metrics import Faithfulness, FactualCorrectness, LLMContextPrecisionWithReference
    from ragas.run_config import RunConfig

    calls = CachedCompatibleCalls(OUT, JUDGE_PROVIDER, JUDGE_MODEL, require_json=True)
    cases = {c["id"]: c for c in json.loads((OUT / "questions.json").read_text("utf-8"))}
    path = OUT / "results.json"
    answers = json.loads((OUT / "answers.json").read_text("utf-8"))
    saved = {(r["case_id"], r["variant"]): r for r in (
        json.loads(path.read_text("utf-8")) if path.exists() else [])}
    rows = []
    for answer in answers:
        prior = saved.get((answer["case_id"], answer["variant"]))
        identical = prior and all(prior.get(k) == answer.get(k) for k in (
            "answer", "contexts", "generator_provider", "generator_model"))
        rows.append(prior if identical else dict(answer))

    class Judge(BaseRagasLLM):
        def generate_text(self, prompt, n=1, temperature=0, stop=None, callbacks=None):
            return LLMResult(generations=[[Generation(text=calls.text(prompt.to_string())) for _ in range(n)]])

        async def agenerate_text(self, prompt, n=1, temperature=0, stop=None, callbacks=None):
            return await asyncio.to_thread(self.generate_text, prompt, n, temperature, stop, callbacks)

        def is_finished(self, response):
            return True

    judge = Judge(run_config=RunConfig(timeout=300, max_retries=1))
    semaphore = asyncio.Semaphore(4)

    async def one(row):
        if "error" in row:
            return
        async with semaphore:
            row["judge_provider"] = JUDGE_PROVIDER
            row["judge_model"] = JUDGE_MODEL
            sample = SingleTurnSample(user_input=row["question"], response=row["answer"],
                retrieved_contexts=[d["text"] for d in row["contexts"]], reference=cases[row["case_id"]]["reference"])
            for name, metric in [("faithfulness", Faithfulness(llm=judge)),
                                 ("context_precision", LLMContextPrecisionWithReference(llm=judge)),
                                 ("factual_correctness", FactualCorrectness(llm=judge, mode="f1"))]:
                if row.get(name) is not None:
                    continue
                try:
                    value = await metric.single_turn_ascore(sample, timeout=300)
                    row[name] = float(value) if math.isfinite(value) else None
                    row.pop(name + "_error", None)
                    print("SCORED", row["case_id"], row["variant"], name, row[name], flush=True)
                except Exception as error:
                    row[name + "_error"] = str(error).replace(calls.key, "[redacted]")[:500]
                    print("SCORE_FAILED", row["case_id"], row["variant"], name, type(error).__name__, flush=True)
                write_json(path, rows)
    await asyncio.gather(*(one(row) for row in rows))


def report():
    rows = json.loads((OUT / "results.json").read_text("utf-8"))
    cases = json.loads((OUT / "questions.json").read_text("utf-8"))
    metrics = ("faithfulness", "context_precision", "factual_correctness")
    protocol = json.loads((OUT / "protocol.json").read_text("utf-8"))
    required = metrics[:2] if protocol.get("primary_pairing") == "faithfulness_context_precision_only" else metrics
    paired = [c["id"] for c in cases if all(any(r["case_id"] == c["id"] and r["variant"] == v
              and all(r.get(m) is not None for m in required) for r in rows) for v in VARIANTS)]
    factual_paired = [c for c in paired if all(any(r["case_id"] == c and r["variant"] == v
                      and r.get("factual_correctness") is not None for r in rows) for v in VARIANTS)]
    summary = {"requested": len(cases), "paired_case_ids": paired,
               "factual_paired_case_ids": factual_paired,
               "incomplete_case_ids": [c["id"] for c in cases if c["id"] not in paired], "variants": {}}
    for variant in VARIANTS:
        selected = [r for r in rows if r["variant"] == variant and r["case_id"] in paired]
        summary["variants"][variant] = {"n": len(selected), **{
            m: statistics.mean(r[m] for r in selected if r["case_id"] in (
                factual_paired if m == "factual_correctness" else paired))
                if (factual_paired if m == "factual_correctness" else paired) else None for m in metrics}}
    write_json(OUT / "summary.json", summary)
    selected = [r for r in rows if r["variant"] == "hybrid_crag" and r["case_id"] in paired]
    if selected:
        write_json(ROOT / "evaluation_results.json", {
            "available_metrics": ["faithfulness", "context_precision"],
            "metadata": {"variant_label": "Hybrid + CRAG", "cases": len(selected),
                         "contracts": len({c["contract_id"] for c in cases if c["id"] in paired}),
                         "live_aura": True, "generator": protocol["generator"],
                         "judge": protocol["judge"], "sample": "positive-answer curated CUAD sample"},
            "data": [{"question": r["case_id"], "full_question": r["question"],
                      "faithfulness": r["faithfulness"], "context_precision": r["context_precision"]}
                     for r in selected]})
    print(json.dumps(summary), flush=True)


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["development", "freeze", "generate", "score", "report"])
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)
    if args.phase == "freeze": freeze()
    elif args.phase == "development": generate(development=True)
    elif args.phase == "generate": generate()
    elif args.phase == "score": asyncio.run(score())
    else: report()


if __name__ == "__main__":
    main()
