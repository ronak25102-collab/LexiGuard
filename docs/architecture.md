# LexiGuard Architecture

## System Overview

LexiGuard is a three-layer system: **Ingestion**, **Storage**, and **Orchestration**.

```
 User Question
      │
      ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   React UI  │────▶│   FastAPI    │────▶│  LangGraph CRAG │
│  (Frontend) │◀────│   (Backend)  │◀────│    (Agent)      │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                                                   ▼
                                          ┌────────────────┐
                                          │  Neo4j Graph   │
                                          │   Database     │
                                          └────────────────┘
```

## Data Ingestion Pipeline

The ingestion pipeline runs once to build the knowledge graph:

### Step 1: Download (downloader.py)
- Sources CUAD contracts from HuggingFace
- Downloads PDFs to `data/raw/`

### Step 2: Parse (parser.py)
- Converts PDF → Markdown using `pymupdf4llm`
- Preserves document structure: headers, numbering, tables
- Output: clean markdown files in `data/parsed/`

### Step 3: Extract (extractor.py)
- Sends markdown to LLM with Pydantic schema constraints
- Forces structured output: ContractData with parties, clauses, locations
- Identifies cross-references between clauses (MODIFIES, SUPERSEDES, etc.)
- Uses `instructor` library for reliable structured extraction

### Step 4: Build Graph (builder.py)
- Creates Neo4j nodes for each entity type
- Establishes relationships using Cypher MERGE statements
- Creates uniqueness constraints for idempotent re-runs

## Corrective RAG (CRAG) Workflow

The core differentiator — a self-correcting retrieval pipeline:

```
START
  │
  ▼
[Retrieve] ─── Generate Cypher from question
  │              Execute against Neo4j
  │              Return graph context
  ▼
[Grade Relevance] ─── LLM evaluates: "Does this context
  │                     actually answer the question?"
  │
  ├── YES ──▶ [Generate] ──▶ Grounded answer with citations ──▶ END
  │
  ├── NO (retries < 3) ──▶ [Rewrite Query] ──▶ Back to [Retrieve]
  │
  └── NO (retries ≥ 3) ──▶ [Generate with Disclaimer] ──▶ END
```

### Why This Matters
- **Self-verification**: The agent doesn't trust its first retrieval blindly
- **Dynamic reformulation**: Failed queries are rewritten for better results
- **Bounded loops**: Maximum 3 retries prevents infinite loops
- **Transparency**: Every answer shows the Cypher query and retry count

## Neo4j Graph Schema

See [graph_schema.md](graph_schema.md) for the full schema documentation.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | API & Neo4j health check |
| POST | `/process` | Run CRAG agent on a legal question |
| GET | `/contracts` | List all contracts |
| GET | `/contracts/{id}` | Full contract detail with graph data |
| GET | `/graph/stats` | Node and relationship counts |

## Frontend Pages

1. **Dashboard** — Contract cards grid with graph statistics
2. **Contract Explorer** — Interactive force-directed graph visualization
3. **Query Interface** — Chat-style legal Q&A with citations
4. **Evaluation Dashboard** — Ragas metrics visualization
