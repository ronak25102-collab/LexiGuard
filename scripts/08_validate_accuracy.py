"""Compare frozen legacy retrieval against the shared improved retriever on new contracts."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import math
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lexiguard.agent import prompts
from lexiguard.agent.retrieval import rank_candidates, search_query, select_context
from lexiguard.evaluation.focused_ablation import GoogleCalls, digest, write_json

OUT = ROOT / "evaluation_results/accuracy_improvement"
MODEL = "gemini-3.5-flash-lite"
# This case informed the lifecycle-routing repair and is excluded from prospective totals.
DEVELOPMENT_CASE_IDS = {"H04"}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def corpus_and_cases():
    records = json.loads((ROOT / "data/extracted_contracts.json").read_text("utf-8"))
    corpus = {}
    for alias, prefix in (("cybergy", "CybergyHoldingsInc"), ("linkplus", "LinkPlusCorp")):
        c = next(c for c in records if c["source_file"].startswith(prefix))
        clauses = {cl["number"]: cl["text"] for cl in c["clauses"]}
        corpus[alias] = {
            "source_file": c["source_file"], "contract_title": c["title"],
            "contract_id": hashlib.sha256(c["source_file"].encode()).hexdigest(),
            "parties": list(dict.fromkeys(p["name"] for p in c["parties"])),
            "text": (ROOT / "data/parsed" / c["source_file"]).read_text("utf-8"),
            "clauses": clauses,
            "clause_titles": {cl["number"]: cl["title"] for cl in c["clauses"]},
            "clause_types": {cl["number"]: cl["clause_type"] for cl in c["clauses"]},
            "edges": [(e["source_clause"], e["target_clause"], e["relationship"])
                      for e in c["cross_references"]
                      if e["source_clause"] in clauses and e["target_clause"] in clauses],
        }
    specs = [
        ("H01", "cybergy", "Which state's law governs the Marketing Affiliate Agreement involving Cybergy Holdings?", "Nevada law governs the agreement under section 24.", ["24"]),
        ("H02", "cybergy", "For a breach of the company's technology warranty, what is the exclusive remedy and when must the written warranty claim be made?", "Under section 16.2, the company must correct the technology to conform substantially to its current specifications or, at its option, replace noncompliant technology. A warranty claim must be made in writing within 90 days of shipment.", ["16.2"]),
        ("H03", "cybergy", "After termination or cancellation, how soon must MA return copies of technology materials, and may it continue marketing the technology?", "Under section 18.3, MA must return all full or partial copies of technology-related materials within 10 days following termination or cancellation and must immediately stop advertising, marketing, promoting and distributing the technology.", ["18.3"]),
        ("H04", "cybergy", "How long does the initial agreement run, how long are automatic renewals, and what written notice is required to terminate at the end of a term?", "Section 1 runs the initial term until the end of the current calendar year and automatically renews it for successive one-year periods, subject to paragraph 18. Section 18.1 allows either party to terminate at the expiration of a term or renewal term upon 30 days' written notice.", ["1", "18.1"]),
        ("H05", "linkplus", "Which state's law governs the Link Plus and Axiometric affiliate agreement regardless of where it is executed or performed?", "Maryland law governs the agreement regardless of the place of execution and performance, under section 7.4.", ["7.4"]),
        ("H06", "linkplus", "An audit identifies underpayment of more than three percent and the payor's auditor confirms it. Who pays the audit costs, and how soon must the deficiency be paid?", "Under section 3.5.4(d), following confirmation by the payor's auditor, the payor must pay the deficiency and the cost of the payee's audit within 15 days after the payee invoices those amounts and provides standard proof of the time and expenses incurred.", ["3.5.4"]),
        ("H07", "linkplus", "Can either party assign this agreement in whole or in part without the other party's prior written consent?", "No. Section 7.1 requires the other party's prior written consent for assignment of all or part of the agreement.", ["7.1"]),
        ("H08", "linkplus", "Do payments to Axiometric for AMR Product Suite sales under section 3.3 stack on top of separate licensed IP royalty payments for the same products?", "No. Section 3.3.5 states that payments to Axiometric for AMR Product Suite sales are in lieu of licensed IP royalty payments for those products.", ["3.3"]),
    ]
    cases = [{"id": cid, "contract": contract, "question": q, "reference": ref,
              "reference_sections": sections, "cohort": "new_CUAD_contract"}
             for cid, contract, q, ref, sections in specs]
    return corpus, cases


class LoggedCalls(GoogleCalls):
    def text(self, prompt, model=None):
        value = super().text(prompt, model)
        write_json(self.cache / (digest([model or self.model, prompt, 0, 8192]) + ".json"),
                   {"model": model or self.model, "prompt": prompt, "text": value})
        return value


class ImprovedRetrieval:
    def __init__(self, legacy, corpus, calls):
        self.legacy, self.corpus, self.calls = legacy, corpus, calls

    def retrieve(self, contract, question):
        data = self.corpus[contract]
        metadata = {k: data[k] for k in ("contract_id", "contract_title", "parties", "source_file")}
        query = search_query(question)
        vector = self.calls.embed([query], query=True)[0]
        semantic, matrix = self.legacy.semantic[contract]
        order = np.argsort(-(matrix @ vector), kind="stable")
        semantic = [{**semantic[int(i)], **metadata} for i in order]
        graph, matrix = self.legacy.graph[contract]
        order = np.argsort(-(matrix @ vector), kind="stable")
        graph = [{**graph[int(i)], **metadata,
                  "title": data["clause_titles"].get(graph[int(i)]["section"], ""),
                  "clause_type": data["clause_types"].get(graph[int(i)]["section"], "")}
                 for i in order]
        ranked = rank_candidates(question, graph)
        seeds, seen = [], set()
        for doc in ranked:
            if doc["section"] not in seen:
                seeds.append(doc)
                seen.add(doc["section"])
            if len(seeds) == 2:
                break
        linked = []
        for seed in seeds:
            for source, target, relation in data["edges"]:
                neighbor = target if source == seed["section"] else (
                    source if target == seed["section"] else None)
                if neighbor:
                    match = next((d for d in ranked if d["section"] == neighbor), None)
                    if match:
                        linked.append({**match, "linked_to": seed["section"], "relationship": relation})
        return select_context(question, seeds + linked + graph, semantic)


def improved_answer(case, retrieval, calls):
    start = time.perf_counter()
    query, trace, retries = case["question"], [], 0
    while True:
        docs = retrieval.retrieve(case["contract"], query)
        context = "\n\n".join(d["text"] for d in docs)
        relevant = calls.text(prompts.RELEVANCE_GRADING_PROMPT.format(
            question=case["question"], context=context)).strip().lower() == "relevant"
        trace.append({"query": query, "contexts": docs, "relevant": relevant})
        if relevant or retries == 2:
            break
        query = calls.text(prompts.QUERY_REWRITE_PROMPT.format(question=case["question"]))
        retries += 1
    if relevant:
        answer = calls.text(prompts.ANSWER_GENERATION_PROMPT.format(
            question=case["question"], context=context))
    else:
        answer = "I could not retrieve enough evidence to answer this question reliably."
    return {"case_id": case["id"], "variant": "after", "question": case["question"],
            "contract": case["contract"], "cohort": case["cohort"], "answer": answer,
            "contexts": docs, "trace": trace, "rewrites": retries,
            "final_relevant": relevant, "seconds": time.perf_counter() - start}


async def factual_scores(rows, cases, calls):
    import lexiguard.evaluation.evaluate  # noqa: F401
    from langchain_core.outputs import Generation, LLMResult
    from ragas import SingleTurnSample
    from ragas.llms import BaseRagasLLM
    from ragas.metrics import FactualCorrectness
    from ragas.run_config import RunConfig

    class Judge(BaseRagasLLM):
        def generate_text(self, prompt, n=1, temperature=0, stop=None, callbacks=None):
            return LLMResult(generations=[[Generation(text=calls.text(prompt.to_string()))
                                          for _ in range(n)]])

        async def agenerate_text(self, prompt, n=1, temperature=0, stop=None, callbacks=None):
            return await asyncio.to_thread(self.generate_text, prompt, n, temperature, stop, callbacks)

        def is_finished(self, response):
            return True

    judge = Judge(run_config=RunConfig(timeout=120, max_retries=1))
    references = {c["id"]: c["reference"] for c in cases}
    semaphore = asyncio.Semaphore(2)

    async def score(row):
        if "error" in row:
            return
        async with semaphore:
            try:
                value = await FactualCorrectness(llm=judge, mode="f1").single_turn_ascore(
                    SingleTurnSample(response=row["answer"], reference=references[row["case_id"]]),
                    timeout=300)
                row["factual_correctness"] = float(value) if math.isfinite(value) else None
                print("FACTUAL", row["case_id"], row["variant"], value, flush=True)
            except Exception as error:
                row["factual_error"] = str(error).replace(calls.key, "[redacted]")[:500]
            write_json(OUT / "results.json", rows)
    await asyncio.gather(*(score(row) for row in rows))


def summarize(rows, cases):
    metrics = ("faithfulness", "context_precision", "factual_correctness")
    paired = [c["id"] for c in cases if all(any(
        r["case_id"] == c["id"] and r["variant"] == variant
        and all(r.get(m) is not None and math.isfinite(r[m]) for m in metrics) for r in rows)
        for variant in ("before", "after"))]

    def aggregate(ids):
        versions = {}
        for variant in ("before", "after"):
            selected = [r for r in rows if r["variant"] == variant and r["case_id"] in ids]
            versions[variant] = {"n": len(selected), **{
                m: statistics.mean(r[m] for r in selected) if selected else None for m in metrics}}
        return {"case_ids": ids, "versions": versions}

    return {
        "all_validation": aggregate(paired),
        "prospective": aggregate([cid for cid in paired if cid not in DEVELOPMENT_CASE_IDS]),
        "development_case_ids": sorted(DEVELOPMENT_CASE_IDS),
        "incomplete_case_ids": [c["id"] for c in cases if c["id"] not in paired],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summarize-only", action="store_true",
                        help="Recompute paired aggregates from saved scores without API calls.")
    parser.add_argument("--frozen-inputs", action="store_true",
                        help="Use the saved questions and corpus rather than local extraction files.")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.summarize_only:
        rows = json.loads((OUT / "results.json").read_text("utf-8"))
        cases = json.loads((OUT / "questions.json").read_text("utf-8"))
        summary = summarize(rows, cases)
        write_json(OUT / "summary.json", summary)
        print("COMPLETE", json.dumps(summary), flush=True)
        return
    legacy = load_module("legacy_accuracy_runner", OUT / "before_code/runner.py")
    old_prompts = load_module("legacy_accuracy_prompts", OUT / "before_code/prompts.py")
    for name in ("ANSWER_GENERATION_PROMPT", "QUERY_REWRITE_PROMPT", "RELEVANCE_GRADING_PROMPT"):
        setattr(legacy, name, getattr(old_prompts, name))
    if args.frozen_inputs:
        cases = json.loads((OUT / "questions.json").read_text("utf-8"))
        corpus = {p.stem: json.loads(p.read_text("utf-8")) for p in (OUT / "corpus").glob("*.json")}
    else:
        corpus, cases = corpus_and_cases()
    write_json(OUT / "questions.json", cases)
    for name, record in corpus.items():
        write_json(OUT / "corpus" / (name + ".json"), record)
    metadata = {"model": MODEL, "judge": MODEL, "cases": len(cases),
                "questions_sha256": digest(cases), "corpus_hashes": {k: digest(v) for k, v in corpus.items()},
                "max_context_chars": 4500, "max_contexts": 3,
                "protocol": "Two contracts excluded from the earlier pilot; seven prospective cases and H04, a development regression. Offline mechanism replay, not a live Neo4j benchmark.",
                "development_case_ids": sorted(DEVELOPMENT_CASE_IDS),
                "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (ROOT / "src/lexiguard").rglob("*.py")}}
    write_json(OUT / "metadata.json", metadata)
    # Share only the request cache, not prior answers/metric aggregates.
    calls = LoggedCalls(ROOT / "evaluation_results/focused_ablation", MODEL, "gemini-embedding-001")
    baseline = legacy.LocalRetrieval(corpus, calls)
    improved = ImprovedRetrieval(baseline, corpus, calls)
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {}
        for case in cases:
            jobs[pool.submit(legacy.answer_case, case, "hybrid_crag", baseline, calls)] = (case, "before")
            jobs[pool.submit(improved_answer, case, improved, calls)] = (case, "after")
        for future in as_completed(jobs):
            case, variant = jobs[future]
            try:
                row = future.result()
                row["variant"] = variant
                print("ANSWERED", case["id"], variant, flush=True)
            except Exception as error:
                row = {"case_id": case["id"], "variant": variant,
                       "error": str(error).replace(calls.key, "[redacted]")[:500]}
            rows.append(row)
            write_json(OUT / "answers.json", rows)
    print("SCORING_FAITHFULNESS_AND_PRECISION", flush=True)
    awaitable = legacy.score_rows(rows, cases, calls, MODEL)
    asyncio.run(awaitable)
    write_json(OUT / "results.json", rows)
    print("SCORING_REFERENCE_CORRECTNESS", flush=True)
    asyncio.run(factual_scores(rows, cases, calls))
    summary = summarize(rows, cases)
    write_json(OUT / "summary.json", summary)
    print("COMPLETE", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
