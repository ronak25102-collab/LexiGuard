# Historical offline pilot

This report describes the earlier offline replay. It is preserved as a record of
that experiment, not a measurement of the restored cloud application. See
[live_ablation.md](live_ablation.md) for the subsequent live Aura evaluation.

# Focused retrieval ablation

The runner in `scripts/07_focused_ablation.py` performs a controlled **offline**
comparison of four stages:

1. Raw-question vector retrieval.
2. Vector retrieval with query preprocessing.
3. Preprocessed retrieval from a graph-first candidate pool plus semantic matches.
4. The same graph-first retrieval with relevance grading and at most two rewrites.

All stages use the same original answer question, answer prompt, scoped contract,
embedding model, generation model, three-context limit, and maximum 4,500-character
context budget. Successful model calls are cached by model and complete prompt.
Model fallback is disabled. Missing or failed scores are reported, and aggregate
comparisons use only cases complete across every stage.

The frozen set has twelve author-written questions: eight from the local synthetic
Apex/Vortex demo MSA, and four grounded in two public CUAD contracts. References
were checked against the source text before scoring. These are not twelve
independent contracts or an official CUAD QA benchmark. References are only
provided to Ragas scoring, never to retrieval or answer generation.

This harness uses normalized NumPy cosine retrieval and a local adjacency graph.
It does not execute generated Cypher or use the production Chroma collection.
CUAD graph nodes and resolved edges replay the existing extraction output; the
demo MSA graph maps explicit references and exceptions from its text. Missing
endpoints are not invented. Graph fragments can occupy every context slot, so the
graph-first stages do not guarantee that a semantic chunk survives selection.

## Run

Install the project's dependencies, configure `LLM_PROVIDER=google` and your
`GOOGLE_API_KEY`, and have the local parsed contracts and extraction JSON available:

```powershell
uv sync
uv run python scripts/07_focused_ablation.py --model gemini-3.5-flash-lite --judge gemini-3.5-flash-lite
```

Outputs are saved under `evaluation_results/focused_ablation/`: frozen questions
and corpus snapshots, model/version/hash metadata, answers and retry traces,
Ragas results, summaries, a Markdown report, and a request cache. No API key is
written to these artifacts.

Replay from snapshots, without the original parsed directory:

```powershell
uv run python scripts/07_focused_ablation.py --model gemini-3.5-flash-lite --judge gemini-3.5-flash-lite --corpus evaluation_results/focused_ablation/corpus --questions evaluation_results/focused_ablation/questions.json
```

## Interpretation

Ragas faithfulness measures support for answer claims in the retrieved context;
context precision measures the relevance and ordering of contexts against the
reference. Neither alone proves a legally correct answer or complete retrieval.
In scenario questions, user-supplied amounts, named parties, or events may be
missing from retrieved fragments and be marked unsupported by the faithfulness
judge. Conversely, a claim that the entire contract is silent can receive a high
faithfulness score when the retrieval missed a real clause. Review raw traces and
reference answers alongside the scores.

This small single-run pilot is descriptive. A common generator and judge, graph
extraction gaps, differing source-unit lengths within a shared maximum budget,
and cached request timings limit interpretation. It is a mechanism ablation in a
local harness, not a historical commit comparison or a live deployment benchmark.
