"""Offline, source-frozen retrieval ablation; never a claim about the live deployment.

The local graph replays extracted edges and explicit references in the demo MSA.
Google calls have a single pinned model, no silent fallback, and a disk cache.
Reference answers are used exclusively by the evaluator, never by retrieval.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import httpx
from langchain_text_splitters import RecursiveCharacterTextSplitter

from lexiguard.agent.prompts import (
    ANSWER_GENERATION_PROMPT,
    QUERY_REWRITE_PROMPT,
    RELEVANCE_GRADING_PROMPT,
)
from lexiguard.config import PARSED_DATA_DIR, PROJECT_ROOT, get_settings

VARIANTS = ("vector_raw", "vector_preprocessed", "hybrid", "hybrid_crag")
CONTEXT_CHARS = 4500
TOP_K = 3
MAX_REWRITES = 2


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), "utf-8")
    # Windows/OneDrive readers can briefly deny replacement of a cached file.
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def parse_msa(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"\*\s*\*\*(\d+\.\d+)\b", text))
    clauses = {}
    for i, match in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = text[match.start():end].split("---")[0].split("**IN WITNESS")[0]
        clauses[match.group(1)] = body.strip()
    return clauses


def load_corpus() -> dict[str, dict]:
    msa_path = sorted(PARSED_DATA_DIR.glob("*MASTER SOFTWARE*md"))[0]
    msa = msa_path.read_text("utf-8")
    corpus = {
        "msa_demo": {
            "source_file": msa_path.name, "provenance": "synthetic local demo contract",
            "text": msa, "clauses": parse_msa(msa),
            "edges": [
                ("3.2", "3.3", "REFERENCES"), ("3.2", "11.2", "REFERENCES"),
                ("3.3", "3.2", "EXCLUDES"), ("3.3", "2.2", "REFERENCES"),
                ("3.3", "11.1", "REFERENCES"), ("7.2", "7.1", "EXCLUDES"),
                ("7.2", "5.2", "REFERENCES"), ("7.2", "6.1", "REFERENCES"),
                ("7.2", "6.2", "REFERENCES"), ("8.3", "8.2", "MODIFIES"),
                ("11.2", "3.3", "REFERENCES"),
            ],
        }
    }
    extracted = json.loads((PROJECT_ROOT / "data/extracted_contracts.json").read_text("utf-8"))
    for alias, prefix in (("ediets", "EdietsComInc"), ("tube", "TubeMediaCorp")):
        record = next(c for c in extracted if c["source_file"].startswith(prefix))
        text = (PARSED_DATA_DIR / record["source_file"]).read_text("utf-8")
        # Match GraphBuilder's MERGE semantics: the last same-number clause wins.
        clauses = {c["number"]: c["text"] for c in record["clauses"]}
        edges = [(e["source_clause"], e["target_clause"], e["relationship"])
                 for e in record["cross_references"]
                 if e["source_clause"] in clauses and e["target_clause"] in clauses]
        corpus[alias] = {
            "source_file": record["source_file"], "provenance": "public CUAD contract",
            "text": text, "clauses": clauses, "edges": edges,
            "unresolved_edges": len(record["cross_references"]) - len(edges),
        }
    return corpus


def make_cases(corpus: dict) -> list[dict]:
    specs = [
        ("Q01", "msa_demo", "cross_clause", "We paid Vortex $40,000 for the payment gateway milestone and delivery is eight calendar days late because Apex did not grant the required API access. Does the 1.5% daily late-delivery penalty still apply?", "The late penalty in section 3.2 is null and void if the delay is directly attributable to the client's failure to grant API access, under section 3.3(a).", ["3.2", "3.3"]),
        ("Q02", "msa_demo", "direct", "A $40,000 milestone is twenty calendar days late due solely to the vendor, with no exemption. What late-delivery penalty follows from the contract?", "Section 3.2 charges 1.5% of the milestone fee per calendar day, capped at 20% of that milestone fee. Twenty days gives 30%, so the applicable cap is $8,000.", ["3.2"]),
        ("Q03", "msa_demo", "cross_clause", "A pandemic delayed a $35,000 milestone by nine days. The vendor first gave written notice seventy-two hours after the event. Does that notice satisfy the contractual requirement to invoke the force-majeure late-penalty exemption?", "No. Section 11.2 requires written notice within forty-eight hours to invoke relief under section 3.3(b). Notice at seventy-two hours does not satisfy that requirement.", ["3.3", "11.2"]),
        ("Q04", "msa_demo", "cross_clause", "Apex paid Vortex $60,000 in the preceding six months. An unauthorized confidentiality disclosure causes a $900,000 claim. Is the contractual liability cap $60,000 or a different amount?", "Section 7.2 excludes confidentiality breaches from the general six-month fees cap in section 7.1 and instead specifies a $500,000 confidentiality super-cap.", ["7.1", "7.2"]),
        ("Q05", "msa_demo", "cross_clause", "A third party makes a $750,000 patent-infringement claim about the deliverables. Does the general cap based on fees paid over six months apply to the vendor's indemnification obligation?", "No. The vendor's third-party infringement indemnity is in section 6.1. Section 7.2 excludes section 6 indemnification obligations from the general section 7.1 liability cap. The $500,000 super-cap is stated for confidentiality breaches, not indemnification.", ["6.1", "7.1", "7.2"]),
        ("Q06", "msa_demo", "cross_clause", "The client wants to terminate for convenience with thirty days' written notice before milestone M-103 is complete. Is notice alone sufficient to avoid an additional termination fee?", "Section 8.2 permits convenience termination on thirty days' prior written notice, but section 8.3 requires a $15,000 termination fee if termination occurs before completion of M-103.", ["8.2", "8.3"]),
        ("Q07", "msa_demo", "direct", "When must the client pay undisputed invoices?", "Undisputed invoices are payable Net-30 from receipt by the client, under section 3.1.", ["3.1"]),
        ("Q08", "msa_demo", "direct", "Which state's law governs the Apex and Vortex agreement?", "The agreement is governed by the laws of the State of Delaware, under section 9.1.", ["9.1"]),
        ("Q09", "ediets", "cross_clause", "eDiets usually pays the monthly fee under section 6.1. Women.com underdelivered advertising and eDiets agreed to a Make Good Period instead of terminating. Must the monthly fee remain unchanged during that period?", "No. Section 6.1 makes the monthly fee subject to adjustments in section 3.1. If eDiets extends the agreement through the Make Good Period, the monthly fee is recalculated and reduced to reflect changes in the revised delivery schedule.", ["6.1", "3.1"]),
        ("Q10", "ediets", "direct", "What is the governing law of the eDiets and Women.com co-branding agreement?", "California law governs interpretation and enforcement, without giving effect to choice-of-law provisions requiring another state's law, under section 15.3.", ["15.3"]),
        ("Q11", "tube", "cross_clause", "The affiliate has exclusive broadcast rights under section 3(a). Does that automatically permit sublicensing the service or distributing it on a video-on-demand basis?", "No. Section 3(c) prohibits subdistribution or sublicensing and distribution using technologies other than Broadcast Television, including video-on-demand, except as expressly provided in section 3(a). Section 3(a) expressly permits authorizing carriage by MVPDs in the station's DMA with the Primary Feed.", ["3(a)", "3(c)"]),
        ("Q12", "tube", "direct", "How much advance written notice must the affiliate provide to stop the automatic renewal?", "The affiliate must provide written notice at least six months before expiration of the Initial Term or the applicable Renewal Term, under section 2(b).", ["2(b)"]),
    ]
    cases = []
    for case_id, contract, cohort, question, reference, sections in specs:
        cases.append({"id": case_id, "contract": contract, "cohort": cohort,
                      "question": question, "reference": reference,
                      "reference_sections": sections,
                      "reference_provenance": "author-written, checked against source contract"})
    return cases


def neighbors(clauses: dict, edges: list, seed: str) -> list[str]:
    """Include incoming overrides as well as outgoing references, within one hop."""
    found = []
    for source, target, kind in sorted(edges, key=lambda e: e[2] == "REFERENCES"):
        candidate = target if source == seed else source if target == seed else None
        if candidate and candidate in clauses and candidate != seed and candidate not in found:
            found.append(candidate)
    return found


def cap_context(docs: list[dict]) -> list[dict]:
    selected, seen, remaining = [], set(), CONTEXT_CHARS
    for doc in docs:
        if remaining <= 0 or len(selected) >= TOP_K:
            break
        if doc["text"] in seen:
            continue
        seen.add(doc["text"])
        text = doc["text"][:min(1500, remaining)]
        if text:
            selected.append({**doc, "text": text})
            remaining -= len(text)
    return selected


class GoogleCalls:
    def __init__(self, output: Path, model: str, embedding_model: str):
        from google import genai
        from google.genai import types
        self.types = types
        self.model = model
        self.embedding_model = embedding_model
        self.key = get_settings().google_api_key
        if not self.key:
            raise ValueError("GOOGLE_API_KEY is required for the Google adapter")
        self.client = genai.Client(api_key=self.key, http_options=types.HttpOptions(timeout=60000))
        self.cache = output / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)

    def request(self, function, **kwargs):
        for attempt in range(4):
            try:
                return function(**kwargs)
            except Exception as error:
                message = str(error)
                delay = re.search(r"retry in ([\d.]+)s", message, re.I)
                transient = isinstance(error, httpx.TimeoutException) or any(
                    code in message for code in ("503 UNAVAILABLE", "500 INTERNAL", "502 BAD_GATEWAY")
                )
                rate_limited = "429" in message and delay is not None
                if not (transient or rate_limited) or attempt == 3:
                    raise
                seconds = min(60, float(delay.group(1)) + 2) if rate_limited else 2 ** (attempt + 1)
                print("PROVIDER_RETRY_WAIT", type(error).__name__, round(seconds, 1), "seconds", flush=True)
                time.sleep(seconds)

    def text(self, prompt: str, model: str | None = None) -> str:
        model = model or self.model
        path = self.cache / (digest([model, prompt, 0, 8192]) + ".json")
        if path.exists():
            return json.loads(path.read_text("utf-8"))["text"]
        response = self.request(self.client.models.generate_content,
            model=model, contents=prompt,
            config=self.types.GenerateContentConfig(temperature=0, max_output_tokens=8192),
        )
        if not response.text or str(response.candidates[0].finish_reason).split(".")[-1] != "STOP":
            raise RuntimeError("Model returned empty or incomplete output")
        write_json(path, {"text": response.text})
        return response.text.strip()

    def embed(self, texts: list[str], query: bool = False) -> np.ndarray:
        task = "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"
        path = self.cache / (digest([self.embedding_model, texts, task, 768]) + ".json")
        if path.exists():
            values = json.loads(path.read_text("utf-8"))
        else:
            values = []
            for start in range(0, len(texts), 50):
                batch = texts[start:start + 50]
                batch_path = self.cache / (digest([self.embedding_model, batch, task, 768, "batch"]) + ".json")
                if batch_path.exists():
                    batch_values = json.loads(batch_path.read_text("utf-8"))
                else:
                    result = self.request(self.client.models.embed_content,
                        model=self.embedding_model, contents=batch,
                        config=self.types.EmbedContentConfig(task_type=task, output_dimensionality=768),
                    )
                    batch_values = [e.values for e in result.embeddings]
                    write_json(batch_path, batch_values)
                values.extend(batch_values)
            write_json(path, values)
        matrix = np.asarray(values, dtype=np.float64)
        return matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)


class LocalRetrieval:
    def __init__(self, corpus: dict, calls: GoogleCalls):
        self.corpus, self.calls = corpus, calls
        splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
        self.semantic, self.graph = {}, {}
        for name, contract in corpus.items():
            docs = [{"text": text, "kind": "semantic", "section": None}
                    for text in splitter.split_text(contract["text"])]
            self.semantic[name] = (docs, calls.embed([d["text"] for d in docs]))
            clauses = [{"text": f"Section {number}: {chunk}", "kind": "graph", "section": number}
                       for number, text in contract["clauses"].items()
                       for chunk in splitter.split_text(text)]
            self.graph[name] = (clauses, calls.embed([d["text"] for d in clauses]))

    def retrieve(self, contract: str, query: str, hybrid: bool) -> list[dict]:
        vector = self.calls.embed([query], query=True)[0]
        docs, matrix = self.semantic[contract]
        order = np.argsort(-(matrix @ vector), kind="stable")
        semantic = [docs[int(i)] for i in order[:TOP_K]]
        if not hybrid:
            return cap_context(semantic)
        clauses, matrix = self.graph[contract]
        order = np.argsort(-(matrix @ vector), kind="stable")
        candidates = []
        seed_sections = set()
        for idx in order:
            seed = clauses[int(idx)]
            if seed["section"] in seed_sections:
                continue
            seed_sections.add(seed["section"])
            candidates.append(seed)
            for neighbor in neighbors(
                self.corpus[contract]["clauses"], self.corpus[contract]["edges"], seed["section"]
            ):
                # Rank fragments inside linked nodes using the same query embeddings.
                candidates.append(next(clauses[int(i)] for i in order
                                       if clauses[int(i)]["section"] == neighbor))
            if len(seed_sections) == 2:
                break
        # A graph seed and its linked clauses take precedence, then semantic matches fill gaps.
        return cap_context(candidates + semantic)


def preprocess(question: str, calls: GoogleCalls) -> str:
    prompt = (
        "Extract concise legal search terms and party names from this question. "
        "Preserve the legal topic, exceptions, causal conditions and section references. "
        "Remove conversational filler and hypothetical amounts. Return only the search text.\n"
        + question
    )
    return calls.text(prompt)


def answer_case(case: dict, variant: str, retrieval: LocalRetrieval, calls: GoogleCalls) -> dict:
    start = time.perf_counter()
    original = case["question"]
    query = original if variant == "vector_raw" else preprocess(original, calls)
    trace, relevant, rewrites = [], None, 0
    while True:
        docs = retrieval.retrieve(case["contract"], query, variant in ("hybrid", "hybrid_crag"))
        context = "\n\n".join(d["text"] for d in docs)
        if variant == "hybrid_crag":
            verdict = calls.text(RELEVANCE_GRADING_PROMPT.format(question=original, context=context))
            relevant = verdict.strip().lower() == "relevant"
        trace.append({"query": query, "relevant": relevant, "contexts": docs})
        if variant != "hybrid_crag" or relevant or rewrites >= MAX_REWRITES:
            break
        rewritten = calls.text(QUERY_REWRITE_PROMPT.format(question=original + "\nPrevious search: " + query))
        query = preprocess(rewritten, calls)
        rewrites += 1
    # Keep the original question and the same answer prompt in every variant.
    prompt = ANSWER_GENERATION_PROMPT.format(question=original, context=context)
    response = calls.text(prompt)
    return {"case_id": case["id"], "variant": variant, "question": original,
            "contract": case["contract"], "cohort": case["cohort"],
            "answer": response, "contexts": docs, "trace": trace,
            "rewrites": rewrites, "final_relevant": relevant,
            "seconds": round(time.perf_counter() - start, 3)}


async def score_rows(rows: list[dict], cases: list[dict], calls: GoogleCalls, judge: str) -> None:
    # Reuse the existing project's compatibility shim for Ragas's retired VertexAI import.
    import lexiguard.evaluation.evaluate  # noqa: F401
    from langchain_core.outputs import Generation, LLMResult
    from ragas import SingleTurnSample
    from ragas.llms import BaseRagasLLM
    from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference
    from ragas.run_config import RunConfig

    class Judge(BaseRagasLLM):
        def generate_text(self, prompt, n=1, temperature=0, stop=None, callbacks=None):
            return LLMResult(generations=[[Generation(text=calls.text(prompt.to_string(), judge))
                                          for _ in range(n)]])

        async def agenerate_text(self, prompt, n=1, temperature=0, stop=None, callbacks=None):
            return await asyncio.to_thread(self.generate_text, prompt, n, temperature, stop, callbacks)

        def is_finished(self, response):
            return True  # GoogleCalls.text already rejects truncated/non-STOP output.

    llm = Judge(run_config=RunConfig(timeout=90, max_retries=1, max_workers=2))
    references = {c["id"]: c["reference"] for c in cases}
    semaphore = asyncio.Semaphore(2)

    async def score(row):
        if "error" in row:
            return
        async with semaphore:
            try:
                sample = SingleTurnSample(user_input=row["question"], response=row["answer"],
                                         retrieved_contexts=[d["text"] for d in row["contexts"]],
                                         reference=references[row["case_id"]])
                faithfulness = Faithfulness(llm=llm)
                precision = LLMContextPrecisionWithReference(llm=llm)
                scores = await asyncio.gather(
                    faithfulness.single_turn_ascore(sample, timeout=120),
                    precision.single_turn_ascore(sample, timeout=120),
                )
                row["faithfulness"], row["context_precision"] = [
                    float(s) if math.isfinite(s) else None for s in scores
                ]
                print("SCORED", row["case_id"], row["variant"], scores, flush=True)
            except Exception as error:
                row["evaluation_error"] = str(error).replace(calls.key, "[redacted]")[:500]
                print("SCORE_FAILED", row["case_id"], row["variant"], type(error).__name__, flush=True)

    await asyncio.gather(*(score(row) for row in rows))


def summarize(rows: list[dict]) -> dict:
    # Common complete cases only: a failed variant can never silently improve its average.
    case_ids = sorted({r["case_id"] for r in rows})
    paired = [cid for cid in case_ids if all(any(
        r["case_id"] == cid and r["variant"] == variant
        and r.get("faithfulness") is not None and r.get("context_precision") is not None
        for r in rows) for variant in VARIANTS)]
    summary = {"paired_case_ids": paired, "requested_cases": len(case_ids), "variants": {}}
    for variant in VARIANTS:
        selected = [r for r in rows if r["variant"] == variant and r["case_id"] in paired]
        summary["variants"][variant] = {
            "n": len(selected),
            **{m: statistics.mean(r[m] for r in selected) if selected else None
               for m in ("faithfulness", "context_precision", "seconds", "rewrites")},
        }
    return summary


def report(summary: dict, rows: list[dict], metadata: dict) -> str:
    text = "# LexiGuard focused offline ablation\n\n"
    text += "This is an offline retrieval experiment, not an evaluation of the deployed Neo4j service.\n\n"
    text += "## Protocol\n\n"
    text += f"- Frozen cases: {metadata['cases']} (8 synthetic demo MSA questions; 4 questions grounded in 2 public CUAD contracts). References were written and checked before scoring.\n"
    text += "- Single pass per variant; descriptive pilot results, no statistical significance claim.\n"
    text += f"- Generator: `{metadata['generator']}`; Ragas judge: `{metadata['judge']}`; temperature 0, no model fallback.\n"
    text += f"- Embeddings: `{metadata['embedding']}`, 768 dimensions, normalized cosine similarity.\n"
    text += "- Contract scope fixed in all arms. Semantic chunks: 1,500 characters, overlap 200; top 3 contexts, maximum 4,500 context characters in every arm.\n"
    text += "- Hybrid seeds use semantic matching against clause fragments, then traverse incoming/outgoing links one hop and rank linked-node fragments by the same query; this replaces live generated Cypher for local replay. Graph fragments use the same 1,500/200 splitting and per-context character limit.\n"
    text += "- Graphs: existing extracted CUAD nodes/edges, with unresolved edges omitted as in GraphBuilder; explicit demo MSA references and exceptions were mapped from its source.\n"
    text += "- CRAG uses the project's relevance and rewrite prompts, at most 2 rewrites, final-pass context only. Original question and answer prompt stay fixed.\n"
    text += "- Every variant uses the same corpus and references. References and expected sections are never passed to retrieval, preprocessing, generation, or CRAG.\n"
    text += "- Faithfulness and LLMContextPrecisionWithReference use actual Ragas metric implementations. Faithfulness alone does not establish correctness against the reference answer.\n"
    text += f"- Ragas version: `{metadata['versions']['ragas']}`. Request cache enables exact replay and avoids duplicate paid calls; timings can include cache hits and are not an uncached latency benchmark.\n\n"
    text += "## Results\n\n| Variant | Paired n | Faithfulness | Context precision | Mean rewrites |\n|---|---:|---:|---:|---:|\n"
    for variant, scores in summary["variants"].items():
        fmt = lambda val: f"{val:.4f}" if val is not None else "unavailable"
        text += f"| {variant} | {scores['n']} | {fmt(scores['faithfulness'])} | {fmt(scores['context_precision'])} | {fmt(scores['rewrites'])} |\n"
    text += f"\nPaired complete cases: {len(summary['paired_case_ids'])}/{summary['requested_cases']}. Errors and undefined scores remain visible in results.json.\n\n"
    text += "## Per-question scores\n\n| Case | Cohort | Variant | Faithfulness | Context precision | Rewrites |\n|---|---|---|---:|---:|---:|\n"
    for row in sorted(rows, key=lambda r: (r["case_id"], VARIANTS.index(r["variant"]))):
        fmt = lambda val: f"{val:.4f}" if val is not None else "unavailable"
        text += f"| {row['case_id']} | {row['cohort']} | {row['variant']} | {fmt(row.get('faithfulness'))} | {fmt(row.get('context_precision'))} | {row.get('rewrites', '-')} |\n"
    text += "\n## Limits and reproduction\n\n"
    text += "The configured Aura database could not be resolved by DNS during preflight. This run uses a local in-memory graph and NumPy cosine retrieval, not Neo4j/ChromaDB end-to-end. It isolates staged mechanisms in a controlled harness rather than measuring a historical production commit. The 8 synthetic questions come from one demo contract and are not independent contracts or a CUAD benchmark. The 4 CUAD-contract questions are author-written, not official CUAD QA annotations. Graph extraction incompleteness and truncated contexts remain possible failure sources. An LLM judge and a small single-run sample limit generalization.\n\n"
    text += f"Run `uv run --no-sync python scripts/07_focused_ablation.py --model {metadata['generator']} --judge {metadata['judge']}` with the local parsed contracts and extracted_contracts.json present and GOOGLE_API_KEY configured. Results include questions.json, metadata.json, results.json, summary.json, frozen corpus snapshots, and cached model responses keyed by model and complete prompt. No API keys are saved.\n"
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "evaluation_results/focused_ablation")
    parser.add_argument("--model", default=get_settings().google_model)
    parser.add_argument("--judge", default="gemini-3.5-flash-lite")
    parser.add_argument("--embedding", default="gemini-embedding-001")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--corpus", type=Path, help="Use frozen corpus JSON snapshots for replay.")
    parser.add_argument("--questions", type=Path, help="Use a frozen questions.json for replay.")
    args = parser.parse_args()
    if get_settings().llm_provider != "google":
        raise SystemExit("This focused harness requires the configured Google provider.")
    output = args.output
    corpus = ({p.stem: json.loads(p.read_text("utf-8")) for p in sorted(args.corpus.glob("*.json"))}
              if args.corpus else load_corpus())
    cases = (json.loads(args.questions.read_text("utf-8")) if args.questions
             else make_cases(corpus))[:args.limit]
    write_json(output / "questions.json", cases)
    for name, data in corpus.items():
        write_json(output / "corpus" / f"{name}.json", data)
    metadata = {"started_utc": datetime.now(timezone.utc).isoformat(), "cases": len(cases),
                "generator": args.model, "judge": args.judge, "embedding": args.embedding,
                "context_chars": CONTEXT_CHARS, "top_k": TOP_K,
                "corpus_hashes": {name: digest(data) for name, data in corpus.items()},
                "questions_sha256": digest(cases),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "versions": {p: importlib.metadata.version(p) for p in ("ragas", "google-genai", "numpy")}}
    write_json(output / "metadata.json", metadata)
    calls = GoogleCalls(output, args.model, args.embedding)
    print("BUILDING_FROZEN_INDEX", flush=True)
    retrieval = LocalRetrieval(corpus, calls)
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(answer_case, case, variant, retrieval, calls): (case, variant)
                for case in cases for variant in VARIANTS}
        for future in as_completed(jobs):
            case, variant = jobs[future]
            try:
                row = future.result()
                print("ANSWERED", case["id"], variant, "rewrites", row["rewrites"], flush=True)
            except Exception as error:
                row = {"case_id": case["id"], "variant": variant, "cohort": case["cohort"],
                       "error": str(error).replace(calls.key, "[redacted]")[:500]}
                print("ANSWER_FAILED", case["id"], variant, type(error).__name__, flush=True)
            rows.append(row)
            write_json(output / "answers.json", rows)
    print("RUNNING_RAGAS", flush=True)
    asyncio.run(score_rows(rows, cases, calls, args.judge))
    write_json(output / "results.json", rows)
    summary = summarize(rows)
    write_json(output / "summary.json", summary)
    (output / "report.md").write_text(report(summary, rows, metadata), "utf-8")
    print("COMPLETE", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
