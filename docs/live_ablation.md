# LexiGuard live ablation and evidence guard validation

## Fresh validation result

24 original CUAD questions from six previously unused public contracts were frozen
after development on the first live pilot. Four production LangGraph variants
used actual Aura reads and the same generator, independent judge, embeddings,
answer prompt and final evidence budget. The sample is curated and positive-answer
only; it is not the full CUAD benchmark or a test of legal reliability.

| Variant | Primary n | Faithfulness | Context precision | Factual F1 |
|---|---:|---:|---:|---:|
| Vector baseline | 24 | 0.959 | 0.729 | 0.515 |
| Hybrid without links | 24 | 0.918 | 0.465 | 0.400 |
| Hybrid with links | 24 | 0.941 | 0.465 | 0.380 |
| Hybrid + CRAG with evidence guard | 24 | 0.934 | 0.729 | 0.490 |

Primary metrics share 24 cases complete across all four variants.
Supplementary factual F1 shares 24 separately complete cases across all
four variants. This separate pairing rule was declared before generation/scoring.
Primary incomplete case IDs: none.
Every attempted case remains in the source audit and raw outputs.

Hybrid + CRAG minus vector: faithfulness -0.025, context precision +0.000.
Exploratory 95% paired contract-cluster bootstrap intervals are
[-0.075, +0.000] and
[+0.000, +0.000], respectively.
The fresh test does not establish a uniform improvement on both requested metrics. Six contract clusters and one run per arm are insufficient to establish
generalization. Even small positive differences should be treated as exploratory.

## Why the implementation changed

The initial live 26-case pilot exposed a real problem: fixed graph-first fusion
displaced complete semantic passages with less useful graph fragments. Its original
joint-complete analysis used 25 cases (one case had undefined supplementary
F1): vector faithfulness 0.940 and precision
0.753, versus CRAG 0.912 and
0.727. This negative pilot is retained in
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

| Variant | All-case n | Literal reference coverage in context | Live cloud reads | Rewrites |
|---|---:|---:|---:|---:|
| Vector baseline | 24 | 0.805 | 24 | 0 |
| Hybrid without links | 24 | 0.592 | 48 | 0 |
| Hybrid with links | 24 | 0.592 | 72 | 0 |
| Hybrid + CRAG with evidence guard | 24 | 0.802 | 78 | 2 |

This supplementary **post-hoc literal coverage** is the case-macro fraction of
distinct normalized reference word 5-grams present in the rendered evidence. It
is not semantic accuracy. References were not supplied to retrieval or generation.
The full source text retains 0.976 of
reference 5-grams. All attempted outputs are included; no favorable-case removal.

Final evidence choices: {'semantic': 22, 'hybrid': 2}. The guard's ability to preserve a strong
vector result is not, by itself, proof that graph retrieval improves it. The
retrieval traces show when graph evidence was actually selected.

Post-hoc illustrations (highest and lowest coverage differences, which can be
zero; not a prespecified success set):

- F24 (Cap On Liability): literal context-coverage change +0.000. Full answers, reference spans, and returned graph rows are in the package.
- F16 (License Grant): literal context-coverage change -0.077. Full answers, reference spans, and returned graph rows are in the package.

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

- Generator: gpt-5.6-luna via CodeCraft, using its reported model name
  without claiming independently authenticated provider identity. Judge:
  nvidia/nemotron-3-super-120b-a12b via NVIDIA NIM. Temperature zero, maximum 8,192 output tokens,
  no silent model fallback.
- Embeddings: gemini-embedding-001, 768 dimensions, normalized. Persistent Chroma
  collection contains 527 chunks across the full saved corpus.
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

The current Aura contains 30 source
records and 1351 clauses. These records include
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
