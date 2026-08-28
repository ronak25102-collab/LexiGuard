# LexiGuard: Enterprise Legal GraphRAG and Compliance Agent

## Overview
LexiGuard is an enterprise-grade Legal GraphRAG platform designed to resolve multi-hop, cross-clause dependencies across commercial contracts. By parsing unstructured legal PDFs into a deterministic Neo4j knowledge graph, LexiGuard enables high-fidelity, self-reflecting Corrective RAG (CRAG) capabilities to eliminate ungrounded legal hallucinations.

## Key Capabilities
* **Knowledge Graph Ingestion:** Automated pipeline converting unstructured legal PDFs into structured Markdown, followed by LLM-driven entity extraction directly mapped to Neo4j nodes (Contract, Party, Clause) and relationships (MODIFIES, SUPERSEDES, EXCLUDES, INCORPORATED_IN).
* **Corrective RAG (CRAG):** Implemented via LangGraph, this architecture evaluates the relevance of retrieved clauses, reformulates Cypher queries upon failure, and synthesizes answers exclusively from grounded legal text.
* **Interactive Web Interface:** A modern, responsive React application featuring light glassmorphism design principles, real-time graph visualization (ForceGraph2D), an interactive chat interface, and a dynamic upload dashboard.
* **Evaluation Suite:** Built-in Ragas integration to continuously measure pipeline accuracy across Faithfulness, Context Precision, and Answer Relevancy.

## System Architecture

```text
[ Legal PDF ] -> [ pymupdf4llm ] -> [ Markdown Text ]
                                          |
                                [ LLM Entity Extraction ]
                                          |
                                 [ Neo4j Graph Database ]
                                          |
[ User Query ] -> [ Cypher Query Generation ] -> [ Clause Retrieval ]
                                                      |
                                         [ Relevance Grading (CRAG) ]
                                            /                  \
                                      [ PASS ]               [ FAIL ]
                                         |                     |
                               [ Synthesize Answer ]  [ Rewrite Query ]
```

## Knowledge Graph Schema

The Neo4j ontology explicitly models commercial contracts:

* **Nodes:** `(Contract)`, `(Party)`, `(Clause)`, `(Location)`
* **Relationships:**
  * `(Contract)-[:HAS_PARTY]->(Party)`
  * `(Contract)-[:CONTAINS_CLAUSE]->(Clause)`
  * `(Clause)-[:INCORPORATED_IN]->(Location)`
  * `(Clause)-[:MODIFIES]->(Clause)`
  * `(Clause)-[:SUPERSEDES]->(Clause)`
  * `(Clause)-[:EXCLUDES]->(Clause)`

## Prerequisites

* Python 3.11+
* Node.js 18+
* Neo4j Aura Account (Free Tier)
* LLM API Keys (OpenAI, Google Gemini, or NVIDIA NIM)

## Quick Start Guide

### 1. Repository Setup

```bash
git clone https://github.com/yourusername/LexiGuard.git
cd LexiGuard

# Backend Setup
pip install -e ".[dev]"

# Frontend Setup
cd frontend
npm install
cd ..

# Environment Configuration
cp .env.example .env
# Edit .env with your Neo4j credentials and LLM API keys
```

### 2. Running the Application

LexiGuard operates with a decoupled frontend and backend. Both must be running simultaneously.

```bash
# Terminal 1: Initialize FastAPI Backend
python -m lexiguard.api.main

# Terminal 2: Initialize React Frontend
cd frontend
npm run dev
```

Navigate to `http://localhost:3000` to access the LexiGuard dashboard.

### 3. Data Ingestion

Contracts can be ingested directly through the web application's **Upload** interface. Alternatively, the CUAD dataset can be bulk-loaded via the provided CLI scripts:

```bash
python scripts/01_download_data.py
python scripts/02_parse_contracts.py
python scripts/03_extract_entities.py
python scripts/04_build_graph.py
```

## Evaluation Framework

LexiGuard utilizes the Ragas framework to validate pipeline integrity. Execute the evaluation suite via:

```bash
python scripts/05_run_evaluation.py
```

* **Faithfulness:** Measures if the generated answer stays grounded in the retrieved legal clauses. (Target: > 0.85)
* **Context Precision:** Measures the signal-to-noise ratio of the retrieved clauses. (Target: > 0.80)
* **Answer Relevancy:** Measures the semantic pertinence of the generated answer to the initial query. (Target: > 0.80)

## Project Structure

```text
LexiGuard/
├── src/lexiguard/
│   ├── config.py              # Configuration schemas
│   ├── ingestion/             # PDF parsing & extraction
│   ├── graph/                 # Neo4j schema & cypher logic
│   ├── agent/                 # LangGraph CRAG workflow
│   ├── evaluation/            # Ragas metric computation
│   └── api/                   # FastAPI routes & controllers
├── frontend/                  # React + Vite application
│   └── src/
│       ├── pages/             # Route components
│       ├── components/        # Reusable UI elements
│       └── api/               # Axios REST clients
├── scripts/                   # CLI execution scripts
├── tests/                     # Pytest test suite
└── docs/                      # Architectural documentation
```

## Technology Stack

* **Data Parsing:** pymupdf4llm
* **LLM Extraction:** OpenAI / Gemini / NVIDIA, Pydantic, Instructor
* **Graph Database:** Neo4j (Cypher)
* **Agentic Orchestration:** LangGraph (Corrective RAG)
* **Backend Application:** FastAPI
* **Frontend Application:** React, Vite, Tailwind CSS, Recharts, ForceGraph2D
* **Metrics & Evaluation:** Ragas

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
