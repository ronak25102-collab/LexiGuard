"""Report the fresh validation and retain the initial negative live pilot."""

from collections import Counter
from pathlib import Path
import csv
import json
import statistics

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evaluation_results/live_guard_validation"
LABELS = {"vector": "Vector baseline", "hybrid_no_links": "Hybrid without links",
          "hybrid": "Hybrid with links", "hybrid_crag": "Hybrid + CRAG with evidence guard"}


def main():
    summary = json.loads((OUT / "summary.json").read_text("utf-8"))
    protocol = json.loads((OUT / "protocol.json").read_text("utf-8"))
    results = json.loads((OUT / "results.json").read_text("utf-8"))
    cases = {q["id"]: q for q in json.loads((OUT / "questions.json").read_text("utf-8"))}
    audit = json.loads((OUT / "source_audit.json").read_text("utf-8"))
    old = json.loads((ROOT / "evaluation_results/live_validation/summary.json").read_text("utf-8"))
    if len(results) != len(cases) * 4:
        raise RuntimeError("All four variants must be attempted before reporting.")
    index = {(r["case_id"], r["variant"]): r for r in results}
    paired = summary["paired_case_ids"]
    factual = summary["factual_paired_case_ids"]
    uncertainty = {"method": "Post-hoc paired contract-cluster percentile bootstrap: 5000 resamples, six clusters, exploratory only", "comparisons": {}}
    rng = np.random.default_rng(20261014)
    for other in ["vector", "hybrid", "hybrid_no_links"]:
        for metric in ["faithfulness", "context_precision", "factual_correctness"]:
            included = factual if metric == "factual_correctness" else paired
            if not included:
                continue
            groups = {}
            for cid in included:
                groups.setdefault(cases[cid]["contract_id"], []).append(cid)
            keys = list(groups)
            diffs = {cid: index[cid, "hybrid_crag"][metric] - index[cid, other][metric] for cid in included}
            draws = [statistics.mean(diffs[cid] for g in rng.choice(keys, len(keys), replace=True)
                                     for cid in groups[g]) for _ in range(5000)]
            uncertainty["comparisons"][f"hybrid_crag_minus_{other}_{metric}"] = {
                "delta": statistics.mean(diffs.values()), "lower_95": float(np.percentile(draws, 2.5)),
                "upper_95": float(np.percentile(draws, 97.5)), "cases": len(included), "contracts": len(keys)}
    (OUT / "uncertainty.json").write_text(json.dumps(uncertainty, indent=2), "utf-8")
    fieldnames = ["case_id", "official_contract_title", "category", "variant", "faithfulness",
                  "context_precision", "factual_correctness", "rewrites", "seconds"]
    with (OUT / "per_query_scores.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(results, key=lambda r: (r["case_id"], r["variant"])):
            writer.writerow({**{k: r.get(k) for k in fieldnames},
                "official_contract_title": cases[r["case_id"]]["official_contract_title"],
                "category": cases[r["case_id"]]["category"]})
    choices = Counter()
    for r in results:
        if r["variant"] == "hybrid_crag" and "error" not in r:
            grades = [t["update"] for t in r["trace"] if t["node"] == "grade_relevance"]
            choices[grades[-1].get("evidence_choice", "unknown")] += 1
    (OUT / "evidence_choices.json").write_text(json.dumps(dict(choices), indent=2), "utf-8")
    scores = summary["variants"]
    table = "| Variant | Primary n | Faithfulness | Context precision | Factual F1 |\n|---|---:|---:|---:|---:|\n"
    for v, label in LABELS.items():
        s = scores[v]
        f1 = f"{s['factual_correctness']:.3f}" if s["factual_correctness"] is not None else "undefined"
        table += f"| {label} | {s['n']} | {s['faithfulness']:.3f} | {s['context_precision']:.3f} | {f1} |\n"
    a = audit["summary"]["variants"]
    coverage_table = "| Variant | All-case n | Literal reference coverage in context | Live cloud reads | Rewrites |\n|---|---:|---:|---:|---:|\n"
    for v, label in LABELS.items():
        s = a[v]
        coverage_table += f"| {label} | {s['n']} | {s['reference_context_5gram_recall']:.3f} | {s['live_queries']} | {s['rewrites']} |\n"
    b, full = scores["vector"], scores["hybrid_crag"]
    df = full["faithfulness"] - b["faithfulness"]
    dp = full["context_precision"] - b["context_precision"]
    ci_f = uncertainty["comparisons"]["hybrid_crag_minus_vector_faithfulness"]
    ci_p = uncertainty["comparisons"]["hybrid_crag_minus_vector_context_precision"]
    # Illustrations are explicitly selected after measuring all cases and include regressions.
    ar = {(r["case_id"], r["variant"]): r for r in audit["rows"]}
    ranked = sorted(cases, key=lambda cid: ar[cid, "hybrid_crag"]["reference_in_context_5gram_recall"]
                                         - ar[cid, "vector"]["reference_in_context_5gram_recall"])
    illustrations = []
    for cid in list(dict.fromkeys([ranked[-1], ranked[0]])):
        delta = ar[cid, "hybrid_crag"]["reference_in_context_5gram_recall"] - ar[cid, "vector"]["reference_in_context_5gram_recall"]
        illustrations.append(f"- {cid} ({cases[cid]['category']}): literal context-coverage change {delta:+.3f}. Full answers, reference spans, and returned graph rows are in the package.")
    old_b, old_f = old["variants"]["vector"], old["variants"]["hybrid_crag"]
    findings = ("The fresh point estimates favor the guarded pipeline on both requested metrics."
                if df > 0.0005 and dp > 0.0005 else
                "The fresh test does not establish a uniform improvement on both requested metrics.")
    markdown = f'''# LexiGuard live ablation and evidence guard validation

## Fresh validation result

24 original CUAD questions from six previously unused public contracts were frozen
after development on the first live pilot. Four production LangGraph variants
used actual Aura reads and the same generator, independent judge, embeddings,
answer prompt and final evidence budget. The sample is curated and positive-answer
only; it is not the full CUAD benchmark or a test of legal reliability.

{table}
Primary metrics share {len(paired)} cases complete across all four variants.
Supplementary factual F1 shares {len(factual)} separately complete cases across all
four variants. This separate pairing rule was declared before generation/scoring.
Primary incomplete case IDs: {', '.join(summary['incomplete_case_ids']) or 'none'}.
Every attempted case remains in the source audit and raw outputs.

Hybrid + CRAG minus vector: faithfulness {df:+.3f}, context precision {dp:+.3f}.
Exploratory 95% paired contract-cluster bootstrap intervals are
[{ci_f['lower_95']:+.3f}, {ci_f['upper_95']:+.3f}] and
[{ci_p['lower_95']:+.3f}, {ci_p['upper_95']:+.3f}], respectively.
{findings} Six contract clusters and one run per arm are insufficient to establish
generalization. Even small positive differences should be treated as exploratory.

## Why the implementation changed

The initial live 26-case pilot exposed a real problem: fixed graph-first fusion
displaced complete semantic passages with less useful graph fragments. Its original
joint-complete analysis used {old_b['n']} cases (one case had undefined supplementary
F1): vector faithfulness {old_b['faithfulness']:.3f} and precision
{old_b['context_precision']:.3f}, versus CRAG {old_f['faithfulness']:.3f} and
{old_f['context_precision']:.3f}. This negative pilot is retained in
evaluation_results/live_validation/, including the excluded case and parser failures.

The CRAG relevance node now compares semantic-only and hybrid candidates before
choosing the evidence for the answer. It keeps complete semantic evidence when
graph retrieval adds only duplicates or unrelated fragments, and selects hybrid
evidence when it adds a substantive provision or exception. It can still rewrite
when neither option supplies the requested provision. Unknown or malformed choices
trigger a retry, not unconditional acceptance of the fused graph context.

Generic search terms were also added for competition, exclusivity and revenue
sharing. Atomic source-heading prefixes prevent the parser from hanging on long
separator lines. These common changes apply to every fresh variant; the evidence
comparison itself applies only to CRAG. This experiment therefore measures the
current pipeline's incremental components, not isolated attribution to every edit.

Development checks through the normal API recovered the audit clause, one-year
renewal with 30-day notice, and previously missed non-compete provision in the
first pilot. Those cases are development evidence and are not counted as fresh
held-out successes. First-pilot and fresh-cohort means must not be compared as an
old-code/new-code effect: the sources and questions differ.

## Source audit

{coverage_table}
This supplementary **post-hoc literal coverage** is the case-macro fraction of
distinct normalized reference word 5-grams present in the rendered evidence. It
is not semantic accuracy. References were not supplied to retrieval or generation.
The full source text retains {a['vector']['reference_source_5gram_recall']:.3f} of
reference 5-grams. All attempted outputs are included; no favorable-case removal.

Final evidence choices: {dict(choices)}. The guard's ability to preserve a strong
vector result is not, by itself, proof that graph retrieval improves it. The
retrieval traces show when graph evidence was actually selected.

Post-hoc illustrations (highest and lowest coverage differences, which can be
zero; not a prespecified success set):

{chr(10).join(illustrations)}

Ragas faithfulness measures support from retrieved evidence and does not establish
completeness. A faithful answer can miss a provision; an abstention can be properly
grounded while retrieval fails. Raw factual F1 is included but can penalize section
citations and contract labels absent from short CUAD reference spans. The first
pilot's L01 exact-quote/zero-F1 anomaly, full prompts and verdicts are preserved.
Malformed judge JSON is retained and retried with identical input/model parameters.
Completed valid scores are not selectively regenerated. One F24 response omitted
a member comma; a deterministic single-delimiter repair retained the first response
and all original strings/verdicts. No judgment or missing value was inferred. Raw
responses and the earlier incomplete scoring attempt remain in the package.

## Frozen protocol

- Generator: {protocol['generator']} via CodeCraft, using its reported model name
  without claiming independently authenticated provider identity. Judge:
  {protocol['judge']} via NVIDIA NIM. Temperature zero, maximum 8,192 output tokens,
  no silent model fallback.
- Embeddings: gemini-embedding-001, 768 dimensions, normalized. Persistent Chroma
  collection contains {protocol['chroma_chunks']} chunks across the full saved corpus.
- Every final answer receives at most three excerpts and 4,500 rendered characters.
  CRAG may inspect both bounded candidate sets (up to 9,000 characters) and perform
  at most two rewrites. This is not an equal-total-inference-token comparison.
- Same original question and selected contract in every arm. Vector resolves scope
  over Aura without graph-clause retrieval. Hybrid without links adds clauses;
  hybrid adds neighbor traversal; CRAG adds competing-evidence selection/relevance.
- Parameterized Cypher over verified TLS executes in every arm. Offline graph replay
  and local lexical fallback are forbidden in the benchmark. Only model/embedding
  responses may be cached; actual query parameters and rows are recorded.
- Six fresh sources selected lexicographically from unused CUAD contracts with
  15,000-45,000 source characters, at least ten parsed sections and four eligible
  positive categories. First four categories in the declared order, reference length
  at most 2,500 characters. No system outputs informed this selection.
- Fresh sources are original CUAD contract text, not new PDF extraction. Introduction
  metadata uses the generator; clauses and explicit references use source parsing.
  Annotation labels and expected answers enter scoring only. Typed override edges
  are not invented from generic references.

## Verified application and remaining deployment step

The current Aura contains {protocol['graph_stats']['nodes']['Contract']} source
records and {protocol['graph_stats']['nodes']['Clause']} clauses. These records include
repeated synthetic uploads, not thirty independent contracts. No local Neo4j server
was started. The normal API passed cloud connectivity, contract listing/statistics,
48-hour notice and California governing-law checks, then the three evidence-guard
development checks. CodeCraft structured extraction was tested with JSON mode,
because the gateway rejects forced tool choices.

The current test suite passed 62 tests. The frontend build passed with a bundle-size
warning. Render configuration is corrected for the actual Neo4j username setting,
generation and embedding providers, and frontend routing. The hosted service has
not been redeployed or verified: see docs/cloud_deployment.md for configuration and
persistent semantic-index requirements.

## Reproduction package

The package contains frozen questions/protocols, full contract text, source/corpus
snapshots, exact measurement-source files, per-query metrics, answers, executed
Cypher and returned rows, cached requests/responses, parser failures, source audits,
bootstrap calculations, and current application code. Start hashes identify the
measurement source; a separate integrity manifest covers the delivered package.
No credentials or local database-server downloads are included.

To inspect existing results without new inference, run the report/audit phases
against the included files. A fresh live replay requires your own Aura, Google,
CodeCraft and NVIDIA keys, graph/vector restoration, and preservation of the saved
answers/results before regenerating them. Clearing model caches creates a new
single-run measurement and can change the values.

```bash
uv sync --extra dev
uv run python scripts/10_restore_cloud.py
uv run python scripts/11_live_ablation.py generate --output evaluation_results/live_guard_validation
uv run python scripts/11_live_ablation.py score --output evaluation_results/live_guard_validation
uv run python scripts/11_live_ablation.py report --output evaluation_results/live_guard_validation
uv run python scripts/12_source_audit.py --output evaluation_results/live_guard_validation
uv run python scripts/15_guard_report.py
```

CUAD attribution: Dan Hendrycks, Collin Burns, Anya Chen and Spencer Ball,
*CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*, NeurIPS 2021.
[Original repository](https://github.com/The-Atticus-Project/cuad).
Bundled annotation entries are unchanged subsets; this is an independent
application evaluation, not an official CUAD benchmark result.
'''
    (OUT / "report.md").write_text(markdown, "utf-8")
    (ROOT / "docs/live_ablation.md").write_text(markdown, "utf-8")
    print(table)
    print(json.dumps({"faithfulness_delta": df, "precision_delta": dp, "choices": dict(choices)}))


if __name__ == "__main__":
    main()
