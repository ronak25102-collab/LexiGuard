# LexiGuard: Enterprise Legal GraphRAG and Compliance Agent

![LexiGuard Live](https://img.shields.io/badge/Live_Demo-lexiguard--ui.onrender.com-brightgreen?style=for-the-badge&logo=render)

**Live Demo:** [https://lexiguard-ui.onrender.com](https://lexiguard-ui.onrender.com)

## Overview
LexiGuard is an enterprise-grade Legal GraphRAG platform designed to resolve multi-hop, cross-clause dependencies across commercial contracts. By combining a **deterministic Neo4j Knowledge Graph** with the **semantic flexibility of a ChromaDB Vector Database**, LexiGuard enables a powerful Hybrid Retrieval system. This dual-path architecture powers a high-fidelity, self-reflecting Corrective RAG (CRAG) agent that eliminates ungrounded legal hallucinations without losing context to fuzzy synonyms.

## Key Capabilities
* **Dual-Path Ingestion:** Automated pipeline converting unstructured legal PDFs into structured Markdown. The pipeline then splits into two paths:
  * **Path A (Structured):** LLM-driven entity extraction mapped directly to Neo4j nodes (Contract, Party, Clause) and relationships (MODIFIES, SUPERSEDES, EXCLUDES).
  * **Path B (Semantic):** Text chunking and embedding storage in ChromaDB to capture underlying legal meaning and fuzzy phrasing.
* **LLM-Driven Entity Resolution:** A specialized Deduplication Engine intercepts extracted entities and merges contract aliases (e.g., "Apex", "The Client", "Apex Enterprise Solutions") into unified primary Neo4j nodes to prevent graph fragmentation.
* **Hybrid Corrective RAG (CRAG):** Implemented via LangGraph, this architecture queries both Neo4j (via generated Cypher) and ChromaDB simultaneously. It evaluates the combined relevance of retrieved clauses, reformulates queries upon failure, and synthesizes answers exclusively from grounded legal text.
* **Zero-Latency LLM Failover:** Engineered with strict rate-limit bypass mechanisms. If the primary LLM (e.g., Gemini 3.6 Flash) encounters a 429 Too Many Requests error, the pipeline instantly fails over to a high-throughput fallback model (Gemini 3.5 Flash Lite) without dropping the client request.
* **Interactive Web Interface:** A modern, responsive React application featuring fluid route transitions (Framer Motion), real-time graph visualization (ForceGraph2D), an interactive chat interface, and a dynamic upload dashboard.
* **Evaluation Suite:** Built-in Ragas integration to continuously measure pipeline accuracy across Faithfulness, Context Precision, and Answer Relevancy.

## System Architecture

```text
[ Legal PDF ] -> [ pymupdf4llm ] -> [ Markdown Text ]
                                          |
                   ------------------------------------------------
                  |                                                |
      [ LLM Entity Extraction ]                         [ Semantic Chunking ]
                  |                                                |
    [ LLM Entity Resolution ]                                      |
         (Deduplication)                                           |
                  |                                                |
       [ Neo4j Graph Database ]                         [ ChromaDB Vector Store ]
                  |                                                |
                  --------------------------------------------------
                                          |
[ User Query ] ------------------> [ Hybrid Retrieval ]
                                          |
                             [ Relevance Grading (CRAG) ]
                                /                  \
                          [ PASS ]               [ FAIL ]
                             |                      |
                   [ Synthesize Answer ]     [ Rewrite Query ]
```

## Knowledge Graph Schema

The Neo4j ontology explicitly models commercial contracts:

* **Nodes:** (Contract), (Party), (Clause), (Location)
* **Relationships:**
  * (Contract)-[:HAS_PARTY]->(Party)
  * (Contract)-[:CONTAINS_CLAUSE]->(Clause)
  * (Clause)-[:INCORPORATED_IN]->(Location)
  * (Clause)-[:MODIFIES]->(Clause)
  * (Clause)-[:SUPERSEDES]->(Clause)
  * (Clause)-[:EXCLUDES]->(Clause)

## Cloud Deployment Architecture
LexiGuard is fully containerized and configured for CI/CD deployment on **Render** via Infrastructure as Code (
ender.yaml).
* **Backend:** Dockerized FastAPI service leveraging the uv package manager for highly optimized, cached build layers. Exposed via port 10000.
* **Frontend:** React + Vite Single Page Application deployed as a highly cached Static Site with custom Catch-All rewrite rules for client-side routing.

## Prerequisites

* Python 3.12+
* Node.js 18+
* Neo4j Aura Account (Free Tier)
* LLM API Keys (Google Gemini, OpenAI, or NVIDIA NIM)

## Local Setup & Quick Start

### 1. Repository Setup

`ash
git clone https://github.com/yourusername/LexiGuard.git
cd LexiGuard

# Install backend dependencies (managed via uv)
uv sync

# Frontend Setup
cd frontend
npm install
cd ..

# Environment Configuration
cp .env.example .env
# Edit .env with your Neo4j credentials and LLM API keys
`

### 2. Running the Application Locally

LexiGuard operates with a decoupled frontend and backend. Both must be running simultaneously.

`ash
# Terminal 1: Initialize FastAPI Backend
uv run uvicorn src.lexiguard.api.main:app --reload --port 8001

# Terminal 2: Initialize React Frontend
cd frontend
npm run dev
`

Navigate to http://localhost:5173 to access the LexiGuard dashboard.

## Technology Stack

* **Data Parsing:** pymupdf4llm
* **LLM Extraction & Embedding:** Gemini / OpenAI / NVIDIA, Pydantic
* **Graph Database:** Neo4j (Cypher)
* **Vector Database:** ChromaDB (Semantic Retrieval)
* **Agentic Orchestration:** LangGraph (Hybrid Corrective RAG)
* **Backend Application:** FastAPI, Docker, uv
* **Frontend Application:** React, Vite, Tailwind CSS, Framer Motion, ForceGraph2D

## License

This project is licensed under the MIT License. See the \LICENSE\ file for details.


