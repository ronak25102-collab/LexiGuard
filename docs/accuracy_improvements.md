# Historical development validation

This report describes the earlier offline development iteration. Its connection
status and results are historical; the subsequent cloud restoration and separate
evaluation are described in [live_ablation.md](live_ablation.md).

# Retrieval accuracy changes

The source-level governing-law misses have been corrected. A real LangGraph
run, using the local source fallback while Neo4j was unavailable, returned
California with section 15.3 for the eDiets agreement and Maryland with section
7.4 for the Link Plus agreement. The application changes are local and have not
been deployed.

## Implementation

- Rank clause headings and clause types together with body text and semantic
  rank. Preserve the initial-term topic in compound lifecycle questions.
- Use parameterized graph reads and traverse incoming as well as outgoing
  REFERENCES, MODIFIES, SUPERSEDES and EXCLUDES links.
- Reserve semantic source evidence when selecting graph context. Cap selected
  evidence at three contexts and 4,500 characters.
- Resolve selected documents by ID. The UI no longer merges different contracts
  merely because their titles match. Named-party queries are also scoped before
  vector search.
- Keep the original answer question unchanged during query rewrites. Replace
  failed-pass context rather than accumulating stale evidence.
- On insufficient evidence, abstain instead of claiming the whole contract is
  silent. Provider failures return an error rather than fabricated source clauses.
- Bind structured extraction schemas before composing Gemini fallback runnables.
- Align vector metadata IDs with graph IDs. Google embeddings now use
  `gemini-embedding-001`, 768 dimensions, in a separate collection so legacy
  vectors are not silently mixed with a different embedding space.
- Show actual API cross-references in the graph visualization. Relevance checks
  are displayed as categorical results, without invented confidence percentages.
  Example evaluation scores and uncomputed answer-relevancy metrics are no longer
  displayed as measured performance.

## Validation

The comparison used eight further source-checked questions from two public CUAD
contracts absent from the original twelve-question pilot. Both versions used the
same corpus, generator/judge model, embedding model, final context limits and
reference answers. The comparison is an offline mechanism replay rather than a
live Neo4j/ChromaDB benchmark. The improved replay uses the application's shared
ranking and context-selection functions.

H04 exposed a missed initial-term facet and was used to correct routing. It is
therefore a development regression case, not part of the seven prospective cases.
Initial outputs and errors are preserved under `iteration_1/`.

| Metric | Before | After | Prospective cases |
|---|---:|---:|---:|
| Ragas faithfulness | 1.0000 | 1.0000 | 7 |
| Ragas context precision | 0.7381 | 0.8095 | 7 |
| Ragas reference factual F1 | 0.6943 | 0.6514 | 7 |

Context precision improved; the reference-F1 metric declined. This does not
establish an across-the-board accuracy improvement. Raw judge outputs show
reference-scope limitations: a correct Nevada answer was scored zero factual F1
because the short reference did not identify the named Marketing Affiliate
Agreement, and citation details were not represented in the reference. That
limitation does not justify hiding the metric. All raw scores remain available.

Source inspection found the previously missed Maryland answer corrected. Both
before and after answer the other six prospective questions' requested facts.
The separate H04 regression now returns the initial calendar-year term,
successive one-year renewals and thirty days' written notice correctly.

The aggregate over all eight validation cases, including H04, is faithfulness
1.0000 → 0.9792 and context precision 0.7500 → 0.8333. These are small, single-run
descriptive comparisons. They are not statistically established generalization
results or a full CUAD benchmark, and the common generator/judge limits their
independence.

Forty local tests pass, and the frontend production build passes. Test coverage
includes contract scope, evidence retention, retry-state replacement, original
question preservation, abstention, real citation numbers, provider failures,
placeholder metrics and structured fallback composition.

## Reproduce

With the local parsed CUAD contracts and extraction JSON present:

```powershell
uv run --no-sync python scripts/08_validate_accuracy.py --frozen-inputs
```

Set `LLM_PROVIDER=google` and `GOOGLE_API_KEY` in the environment. The runner pins
Gemini 3.5 Flash Lite for generation and judging and uses actual Ragas metrics.
The provider uses fixed sampling defaults; specifying temperature zero is not
a guarantee of determinism. Successful calls are cached to allow exact replay.

Outputs are under `evaluation_results/accuracy_improvement/`: frozen questions
and corpus, before-code snapshots, answers, source contexts, retry traces, raw
metrics, aggregate scores, initial iteration outputs and actual LangGraph smoke
results. The measured changes are not yet deployed. Neo4j connectivity and a
larger independent evaluation remain necessary for production validation.

The accompanying ZIP includes the ignored evaluation inputs, legacy snapshots,
scores and cached requests. Extract it into the repository root before replaying.
To recompute the aggregates without making API calls, run
`uv run --no-sync python scripts/08_validate_accuracy.py --summarize-only`.

Existing Google vectors must be reindexed into the new model/dimension-specific
collection for semantic search. The previous collection is preserved; local
parsed-source retrieval supplies a lexical fallback in the meantime.
Use `uv run --no-sync python scripts/09_reindex_vectors.py --all --dry-run`
to inspect the indexing plan, or select particular Markdown filenames with
repeated `--source-file` options. Remove `--dry-run` to index using the configured
provider. Reindexing calls the embedding API and was not run across the corpus
as part of this validation.
