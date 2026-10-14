# LexiGuard

LexiGuard answers questions about commercial contracts using Neo4j, ChromaDB,
LangGraph, FastAPI, and a React interface. It retrieves source evidence, follows
cross-clause references and overrides, and can rewrite a query when a relevance
check finds insufficient evidence. Answers include excerpts and section citations.

The evaluation scores describe particular datasets and configurations; they do
not establish legal reliability or eliminate hallucinations. See the
[live ablation report](docs/live_ablation.md) for the current experiment and its
limitations. Earlier offline pilots are documented in
[focused_ablation.md](docs/focused_ablation.md) and
[accuracy_improvements.md](docs/accuracy_improvements.md).

The [one-page report](output/pdf/LexiGuard_live_ablation_brief.pdf) summarizes
the measured results. Download the
[reproducibility package](evaluation_results/LexiGuard_live_evaluation_package.zip)
for frozen questions, source snapshots, per-query scores and executed query traces.
The package includes both live runs and an integrity manifest, with credentials
and correspondence excluded.

## How it works

1. Parse a PDF to Markdown and extract contract metadata with an LLM.
2. Supplement extracted clauses with verbatim numbered source sections,
   lettered subclauses, and exhibits. Resolve explicit section references.
3. Store contract, party, clause, and location nodes in Neo4j and text chunks in
   a Chroma collection for the configured embedding model.
4. Resolve contract scope, use parameterized Cypher to retrieve clauses and
   neighboring REFERENCES, MODIFIES, SUPERSEDES, and EXCLUDES relationships,
   and combine that evidence with scoped semantic retrieval.
5. Rank evidence within a context budget, retaining semantic background and
   linked exceptions. CRAG can perform a bounded number of retrieval rewrites.
6. Generate a grounded answer or report insufficient evidence. Upstream failures
   produce errors; the API does not substitute fabricated sample answers.

Typed overrides depend on extraction. A reference does not automatically prove
an override relationship. The source parser supplements explicit references
without inventing MODIFIES or SUPERSEDES edges.

## Setup

Requires Python 3.11+, uv, a recent Node.js version, and a Neo4j instance.
The live evaluation uses AuraDB over verified TLS; a local Neo4j server is not
required. API credentials belong in `.env`, which is ignored by Git.

```bash
uv sync --extra dev
# Copy .env.example to .env and configure credentials.
cd frontend
npm install
```

Generation supports OpenAI, Google Gemini, NVIDIA NIM, and the OpenAI-compatible
CodeCraft gateway. Gateway model names are gateway-reported identities.
Configure EMBEDDING_PROVIDER separately when changing the generator so the
existing vector space remains compatible. Reduced-dimensional Gemini embeddings
use 768 dimensions and unit normalization for documents and queries.

Example configuration (supply your own keys):

```dotenv
LLM_PROVIDER=codecraft
CODECRAFT_MODEL=gpt-5.6-luna
CODECRAFT_BASE_URL=https://codecraftapi.com/v1
EMBEDDING_PROVIDER=google
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=your-instance-username
```

Start the API from the repository root and the UI from `frontend/`:

```bash
uv run uvicorn lexiguard.api.main:app --reload --port 8001
# In a second terminal:
cd frontend
npm run dev
```

The UI development server uses port 3000 and proxies `/api` to the backend.
For deployment, set VITE_API_URL and configure the backend environment separately.
The Dockerfile and render.yaml describe Render deployment; changing this
checkout's `.env` does not update a hosted service.

## Data and indexing

Upload a PDF through the UI or use the numbered scripts to download, parse,
extract, and build a graph. `scripts/09_reindex_vectors.py --all` indexes saved
Markdown. `scripts/10_restore_cloud.py` restores saved source records to the
configured Aura instance, without starting a local Neo4j server.

The saved corpus includes public CUAD contracts and repeated uploads of a
synthetic demonstration contract. Repeated uploads are distinct source records,
not independent evaluation examples. Raw PDFs, parsed Markdown, vector indexes,
and evaluation outputs are ignored by Git and must be obtained or included in
an independent reproduction package.

## Evaluation and checks

```bash
uv run pytest -q
cd frontend
npm run build
```

The live experiment runs production LangGraph retrieval nodes in four modes:
vector-only; hybrid without graph links; hybrid with graph links; and hybrid plus
CRAG. It uses frozen official CUAD questions and answer spans, a pinned generator
and independent judge, fixed embeddings and evidence budgets, and actual cloud
queries. References are supplied only to the evaluator. No offline graph replay
or silent model fallback is allowed in that benchmark.

```bash
# Freeze a new experiment only before inspecting its outcomes.
uv run python scripts/11_live_ablation.py freeze
uv run python scripts/11_live_ablation.py generate
uv run python scripts/11_live_ablation.py score
uv run python scripts/11_live_ablation.py report
uv run python scripts/12_source_audit.py
```

Ragas measures faithfulness and context precision. The live suite also records
factual F1 and a supplementary literal reference-coverage audit. Faithfulness can
be high when retrieved evidence is incomplete; LLM judges can mis-score even exact
source matches. Inspect per-query outputs and traces alongside aggregate scores.

## License

MIT. See [LICENSE](LICENSE).
