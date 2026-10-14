"""Summarize completed measurements without changing generation or retrieval."""

from pathlib import Path
import csv
import json
import statistics

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evaluation_results/live_validation"
LABELS = {"vector": "Vector baseline", "hybrid_no_links": "Hybrid without links",
          "hybrid": "Hybrid with links", "hybrid_crag": "Hybrid + CRAG"}


def main():
    summary = json.loads((OUT / "summary.json").read_text("utf-8"))
    protocol = json.loads((OUT / "protocol.json").read_text("utf-8"))
    results = json.loads((OUT / "results.json").read_text("utf-8"))
    cases = {c["id"]: c for c in json.loads((OUT / "questions.json").read_text("utf-8"))}
    audit = json.loads((OUT / "source_audit.json").read_text("utf-8"))
    index = {(r["case_id"], r["variant"]): r for r in results}
    if len(results) != 104:
        raise RuntimeError("The final report requires all 104 attempted rows")
    fields = ["case_id", "source_file", "category", "variant", "faithfulness",
              "context_precision", "factual_correctness", "rewrites", "seconds"]
    with (OUT / "per_query_scores.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in sorted(results, key=lambda r: (r["case_id"], r["variant"])):
            writer.writerow({**{k: row.get(k) for k in fields},
                             "source_file": cases[row["case_id"]]["source_file"],
                             "category": cases[row["case_id"]]["category"]})
    paired = summary["paired_case_ids"]
    groups = {}
    for case_id in paired:
        groups.setdefault(cases[case_id]["contract_id"], []).append(case_id)
    rng = np.random.default_rng(20261014)
    uncertainty = {"description": "Post-hoc percentile cluster bootstrap, 5000 resamples of contracts, preserving paired questions; six clusters give imprecise exploratory intervals. No significance claim.", "comparisons": {}}
    group_keys = list(groups)
    for other in ["hybrid_no_links", "hybrid", "vector"]:
        for metric in ["faithfulness", "context_precision", "factual_correctness"]:
            differences = {cid: index[cid, "hybrid_crag"][metric] - index[cid, other][metric]
                           for cid in paired}
            samples = []
            for _ in range(5000):
                selected = rng.choice(group_keys, size=len(group_keys), replace=True)
                samples.append(statistics.mean(differences[cid] for g in selected for cid in groups[g]))
            uncertainty["comparisons"][f"hybrid_crag_minus_{other}_{metric}"] = {
                "delta": statistics.mean(differences.values()),
                "lower_95": float(np.percentile(samples, 2.5)),
                "upper_95": float(np.percentile(samples, 97.5)),
                "cases": len(paired), "contracts": len(group_keys)}
    (OUT / "uncertainty.json").write_text(json.dumps(uncertainty, indent=2), "utf-8")
    table = "| Variant | Paired n | Faithfulness | Context precision | Factual F1 |\n|---|---:|---:|---:|---:|\n"
    for variant, label in LABELS.items():
        v = summary["variants"][variant]
        table += f"| {label} | {v['n']} | {v['faithfulness']:.3f} | {v['context_precision']:.3f} | {v['factual_correctness']:.3f} |\n"
    a = audit["summary"]["variants"]
    coverage_table = "| Variant | All-case n | Reference coverage in context | Live cloud reads | Rewrites |\n|---|---:|---:|---:|---:|\n"
    for variant, label in LABELS.items():
        v = a[variant]
        coverage_table += f"| {label} | {v['n']} | {v['reference_context_5gram_recall']:.3f} | {v['live_queries']} | {v['rewrites']} |\n"
    baseline = summary["variants"]["vector"]
    full = summary["variants"]["hybrid_crag"]
    missing = summary["incomplete_case_ids"]
    ci_f = uncertainty["comparisons"]["hybrid_crag_minus_vector_faithfulness"]
    ci_p = uncertainty["comparisons"]["hybrid_crag_minus_vector_context_precision"]
    docs = f'''# Live Aura retrieval ablation

26 official CUAD questions from six public contracts; four variants of the
current shared implementation. All 104 answers used actual cloud Aura queries.
This is an incremental retrieval ablation, not an old-commit versus new-commit
comparison or a claim about the full CUAD benchmark.
The sample and models differ from the earlier offline pilot; compare the paired
variants within this run, not the old and new aggregate scores.

## Ragas results

Scores are case-macro means on the same {len(paired)} cases complete across every
variant and all three metrics. All 26 attempted cases remain in the raw outputs
and source audit. Incomplete paired case IDs: {', '.join(missing) or 'none'}.

{table}
Relative to vector retrieval, Hybrid + CRAG changed faithfulness by
{full['faithfulness']-baseline['faithfulness']:+.3f} and context precision by
{full['context_precision']-baseline['context_precision']:+.3f} on this sample.
Exploratory contract-cluster bootstrap 95% intervals for those changes are
[{ci_f['lower_95']:+.3f}, {ci_f['upper_95']:+.3f}] and
[{ci_p['lower_95']:+.3f}, {ci_p['upper_95']:+.3f}], respectively. Only six contracts
were sampled, so these intervals are imprecise and do not establish generalization.

## Frozen setup

- Original CUAD questions and annotated spans, from six contracts not used in
  the earlier development cases. Positive-answer categories selected in a declared
  order, up to five per contract, with references limited to 2,500 characters.
- Generator: {protocol['generator']} through CodeCraft. This identity is reported
  by the gateway, not independently authenticated. Judge: {protocol['judge']}
  through NVIDIA NIM. Temperature zero, 8,192-token output budget, no model fallback.
- Embeddings: gemini-embedding-001, 768 dimensions, unit normalized; persistent
  Chroma collection with 386 chunks. Same embedding space in every variant.
- Same answer prompt, question, selected contract, maximum three contexts and
  4,500 rendered characters. At most two CRAG rewrites. References only enter scoring.
- Vector baseline still resolves document scope through Aura, but reads no graph
  clauses. Hybrid without links adds graph clause retrieval; Hybrid adds neighboring
  links; Hybrid + CRAG additionally grades relevance and can rewrite retrieval.
- Actual parameterized Cypher reads over verified TLS. Offline graph replay and
  lexical fallback are forbidden by the benchmark. Model and embedding request
  caches are allowed; graph reads execute again even when an answer prompt is cached.
- A Google quota interruption was preserved separately. Before any Ragas scoring,
  all four variants were restarted with the same available generator and independent
  judge. Questions, corpus, embeddings, prompts, ranking and context limits were unchanged.

## Source audit and limitations

{coverage_table}
Coverage is a **post-hoc literal diagnostic**: the fraction of distinct normalized
reference word 5-grams present in the selected context, averaged by question. It
is not semantic accuracy. It includes every attempted case, including abstentions.
Parsed source formatting itself retains {a['vector']['reference_source_5gram_recall']:.3f}
of reference 5-grams. All selected contexts were in scope and matched their stored
contiguous source windows; none exceeded the declared context budget.

Source inspection found both recoveries and regressions:

- L16, audit rights: vector retrieval missed the audit and site-inspection clause;
  graph retrieval supplied Section 6 and the answer recovered both rights.
- L07 and L10: CRAG rewrites recovered assignment and German governing-law clauses
  lost by the initial hybrid stage. The vector baseline already had these clauses;
  these are recoveries from hybrid regressions, not unique wins over vector retrieval.
- L25, renewal: vector retrieval captured successive one-year terms and 30-day
  notice. Hybrid + CRAG selected a truncated fragment and could not recover those
  conditions. This remains a real regression.
- L19, non-compete: every variant missed the annotated restriction. CRAG exhausted
  two rewrites and abstained. This remains a real retrieval miss.
- L01, judge anomaly: every variant quoted the reference governing-law sentence,
  yet raw factual F1 was zero because the judge treated the contract name and section
  citation as unsupported by the short reference span. The verdict and prompts are
  preserved in judge_anomaly_L01.json. Raw scores are retained without selective repair.

One run, six contracts, a curated positive-answer sample, and an LLM judge are
insufficient to claim a general accuracy improvement. Faithfulness evaluates
support from retrieved evidence; it does not establish completeness. A correct
abstention can coexist with failed retrieval. The report retains raw factual F1
and the source audit alongside the two requested Ragas metrics.

## Application validation

Aura was restored to 24 source records, 1,058 clauses and 477 reference links.
The records include repeated synthetic uploads and are not 24 independent contracts.
No local Neo4j server was started. The normal FastAPI path, without benchmark
model/retrieval mocks, passed health, configuration, contract listing, graph statistics,
and source-grounded 48-hour notice and California governing-law checks.
The suite passed 58 tests; the frontend production build passed, with a bundle-size
warning. Render configuration corrections are prepared, but the hosted service
has not been redeployed or verified by this experiment.

## Reproduce and inspect

The package includes questions.json, protocol.json, graph_snapshot.json, corpus
snapshots, answers.json, results.json, per_query_scores.csv, source_audit.csv,
uncertainty.json, and exact cached model requests/responses. Cloud query traces
contain executed Cypher, parameters and returned rows. Measurement source files
match the protocol's start hashes; current application source is separately included.
Post-start changes to embedding normalization align the normal application with
the already-normalized benchmark adapter. API/UI reporting and provider throttling
changes do not alter benchmark questions, ranking, prompts, or context contents.
Malformed judge JSON is preserved and retried with identical input and model;
valid completed scores are not selectively rerun. Structured extraction uses
JSON mode because the gateway rejects forced tool choices.

For a new cloud run, configure your own Aura, CodeCraft, NVIDIA and Google credentials,
restore the graph and vectors, and retain the frozen questions. Preserve the saved
answers/results before rerunning generation. Running against a new endpoint or
clearing model caches creates a new measurement and may change the scores.

```bash
uv sync --extra dev
uv run python scripts/10_restore_cloud.py
uv run python scripts/11_live_ablation.py generate
uv run python scripts/11_live_ablation.py score
uv run python scripts/11_live_ablation.py report
uv run python scripts/12_source_audit.py
uv run python scripts/13_live_report.py
```

The original dataset is [CUAD](https://github.com/The-Atticus-Project/cuad),
by Dan Hendrycks, Collin Burns, Anya Chen and Spencer Ball (NeurIPS 2021).
The bundled annotation file contains unchanged entries for the six selected
contracts, not the entire dataset. Earlier offline experiments remain historical
and are not mixed into these live aggregates.
'''
    (ROOT / "docs/live_ablation.md").write_text(docs, "utf-8")
    (OUT / "report.md").write_text(docs, "utf-8")
    print(table)
    print(json.dumps(uncertainty["comparisons"]["hybrid_crag_minus_vector_context_precision"]))


if __name__ == "__main__":
    main()
