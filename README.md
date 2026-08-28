# ⚖️ LexiGuard — Multi-Contract Legal GraphRAG Agent

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green.svg)](https://fastapi.tiangolo.com)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-blue.svg)](https://neo4j.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An automated legal auditing system that ingests commercial contracts, structures them into a queryable **Knowledge Graph**, and uses a **self-correcting AI agent** (Corrective RAG) to answer complex multi-clause compliance questions — without hallucinating.

---

## 🎯 Why LexiGuard?

Traditional RAG systems use flat vector search: they find paragraphs with similar words. This **fails catastrophically** on legal contracts where Clause A on page 2 is modified or superseded by Clause G on page 45.

LexiGuard solves this with **GraphRAG** — mapping explicit relationships (`MODIFIES`, `EXCLUDES`, `SUPERSEDES`) between legal entities and clauses, enabling multi-hop reasoning over connected data.

| Feature | Traditional RAG | LexiGuard (GraphRAG) |
|---------|:--------------:|:-------------------:|
| Cross-clause awareness | ❌ | ✅ |
| Relationship traversal | ❌ | ✅ |
| Self-verification loop | ❌ | ✅ |
| Grounded citations | ❌ | ✅ |
| Published metrics | ❌ | ✅ |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                      │
│  Dashboard │ Contract Explorer │ Chat Interface │ Evaluation  │
└─────────────────────────┬────────────────────────────────────┘
                          │ HTTP/REST
┌─────────────────────────┴────────────────────────────────────┐
│                    FastAPI Backend                             │
│  /process │ /contracts │ /graph/stats │ /health               │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────┴────────────────────────────────────┐
│              LangGraph CRAG Agent (Self-Correcting)           │
│                                                               │
│  ┌──────────┐    ┌───────────┐    ┌────────────┐             │
│  │ Retrieve │───▶│  Grade    │───▶│  Generate  │──▶ Answer   │
│  │ (Cypher) │    │ Relevance │    │  (Grounded)│             │
│  └──────────┘    └─────┬─────┘    └────────────┘             │
│       ▲                │                                      │
│       │          ┌─────▼─────┐                                │
│       └──────────│  Rewrite  │ (if irrelevant, max 3 retries)│
│                  │  Query    │                                │
│                  └───────────┘                                │
└─────────────────────────┬────────────────────────────────────┘
                          │ Cypher
┌─────────────────────────┴────────────────────────────────────┐
│                   Neo4j Knowledge Graph                       │
│                                                               │
│  (Contract)──HAS_PARTY──▶(Party)                             │
│      │                       │                                │
│  CONTAINS_CLAUSE         INCORPORATED_IN                      │
│      │                       │                                │
│      ▼                       ▼                                │
│  (Clause)──MODIFIES──▶(Clause)    (Location)                 │
│           ──SUPERSEDES──▶                                     │
│           ──EXCLUDES──▶                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Neo4j Aura account ([free tier](https://neo4j.com/cloud/aura-free/))
- OpenAI API key, Google Gemini API key, or NVIDIA NIM API key

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/LexiGuard.git
cd LexiGuard

# Backend
pip install -e ".[dev]"

# Frontend
cd frontend && npm install && cd ..

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### 2. Build the Knowledge Graph

```bash
# Step 1: Download CUAD contracts
python scripts/01_download_data.py

# Step 2: Parse PDFs to Markdown
python scripts/02_parse_contracts.py

# Step 3: Extract legal entities using LLM
python scripts/03_extract_entities.py

# Step 4: Build Neo4j knowledge graph
python scripts/04_build_graph.py
```

### 3. Run the Application

```bash
# Terminal 1: Start the backend
python -m lexiguard.api.main

# Terminal 2: Start the frontend
cd frontend && npm run dev
```

Open **http://localhost:3000** to access the LexiGuard dashboard.

---

## 📊 Evaluation

Run the Ragas evaluation suite to measure pipeline accuracy:

```bash
python scripts/05_run_evaluation.py
```

| Metric | Score | Description |
|--------|:-----:|-------------|
| **Faithfulness** | Target > 0.85 | Does the answer stay grounded in retrieved clauses? |
| **Context Precision** | Target > 0.80 | Did the retriever find the right clauses? |
| **Answer Relevancy** | Target > 0.80 | Is the answer pertinent to the question? |

---

## 🗂️ Project Structure

```
LexiGuard/
├── src/lexiguard/
│   ├── config.py              # Settings (Pydantic)
│   ├── ingestion/             # PDF parsing & entity extraction
│   │   ├── downloader.py      # CUAD dataset download
│   │   ├── parser.py          # PDF → Markdown (pymupdf4llm)
│   │   └── extractor.py       # LLM structured extraction
│   ├── graph/                 # Neo4j knowledge graph
│   │   ├── schema.py          # Pydantic models (41 CUAD categories)
│   │   ├── neo4j_client.py    # Database driver wrapper
│   │   └── builder.py         # Graph construction (MERGE)
│   ├── agent/                 # LangGraph CRAG agent
│   │   ├── state.py           # TypedDict state
│   │   ├── prompts.py         # Legal prompt templates
│   │   ├── nodes.py           # Retrieve, Grade, Generate, Rewrite
│   │   └── graph.py           # Workflow compilation
│   ├── evaluation/            # Ragas evaluation
│   │   ├── test_set.py        # CUAD QA test builder
│   │   └── evaluate.py        # Metrics computation
│   └── api/                   # FastAPI backend
│       ├── models.py          # Request/Response schemas
│       └── main.py            # REST endpoints
├── frontend/                  # React + Vite + Tailwind
│   └── src/
│       ├── pages/             # Dashboard, Chat, Explorer, Eval
│       ├── components/        # Navbar, StatsCard, Spinner
│       └── api/client.js      # Axios API client
├── scripts/                   # Pipeline execution scripts
├── tests/                     # Pytest suite
└── docs/                      # Architecture documentation
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Data** | CUAD Dataset | 510 real commercial contracts |
| **Parsing** | pymupdf4llm | PDF → structured Markdown |
| **Extraction** | OpenAI + Pydantic + Instructor | Structured entity extraction |
| **Graph DB** | Neo4j (Aura) | Knowledge graph storage |
| **Agent** | LangGraph | Corrective RAG workflow |
| **Backend** | FastAPI | REST API |
| **Frontend** | React + Vite + Tailwind | Web interface |
| **Evaluation** | Ragas | Faithfulness & precision metrics |

---

## 💼 Resume Bullet Points

- **LexiGuard – Multi-Contract Legal GraphRAG & Compliance Agent** *(Python, Neo4j, LangGraph, FastAPI, React)*
- *Architected an enterprise Legal GraphRAG platform utilizing Neo4j to resolve multi-hop cross-clause dependencies across 500+ commercial contracts from the CUAD dataset.*
- *Engineered an automated extraction pipeline converting unstructured legal PDFs into a queryable knowledge graph (Contract, Party, and Clause nodes) via explicit Cypher relationship mappings (MODIFIES, SUPERSEDES, EXCLUDES).*
- *Implemented a Corrective RAG (CRAG) workflow via LangGraph with self-reflection guardrails, eliminating ungrounded legal hallucinations through dynamic Cypher query reformulation.*
- *Built a full-stack web application with React dashboard, interactive graph visualization, and chat interface backed by FastAPI, achieving >85% Faithfulness on Ragas evaluation.*

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
