"""FastAPI backend for LexiGuard.

Exposes the LangGraph CRAG agent and Neo4j knowledge graph
through a REST API with OpenAPI documentation.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
import tempfile
import uuid
import json
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from lexiguard.agent.graph import run_agent
from lexiguard.api.models import (
    ContractSummary,
    GraphStats,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SourceDocument,
)
from lexiguard.config import LLMProvider, get_settings, RAW_DATA_DIR, PARSED_DATA_DIR
from lexiguard.graph.neo4j_client import Neo4jClient, get_client
from lexiguard.ingestion.parser import parse_contract
from lexiguard.ingestion.extractor import extract_contract_entities
from lexiguard.graph.builder import GraphBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Module-level client — initialized during lifespan
_neo4j_client: Neo4jClient | None = None

# Semaphore for concurrent upload limiting
_upload_semaphore: asyncio.Semaphore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: connect to Neo4j on startup, close on shutdown."""
    global _neo4j_client, _upload_semaphore
    logger.info("Starting LexiGuard API...")
    
    # Initialize semaphore for rate limiting
    settings = get_settings()
    _upload_semaphore = asyncio.Semaphore(settings.max_concurrent_uploads)
    logger.info(f"Concurrent upload limit: {settings.max_concurrent_uploads}")
    logger.info(f"Chunk limit per contract: {settings.max_chunks_per_contract}")

    _neo4j_client = Neo4jClient()
    try:
        if _neo4j_client.verify_connection():
            logger.info("Neo4j connection verified.")
        else:
            logger.warning("Neo4j connection could not be verified — running in degraded mode.")
    except Exception as e:
        logger.error(f"Neo4j startup error: {e}")

    yield

    logger.info("Shutting down LexiGuard API...")
    if _neo4j_client:
        _neo4j_client.close()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="LexiGuard API",
    description="Multi-Contract Legal GraphRAG & Compliance Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_client() -> Neo4jClient:
    """Get the Neo4j client, raising an error if not initialized."""
    if _neo4j_client is None:
        raise HTTPException(status_code=503, detail="Neo4j client not initialized")
    return _neo4j_client


def _is_rate_limited(error: Exception) -> bool:
    """Return whether an upstream LLM provider rejected the request for quota."""
    message = str(error).lower()
    return any(term in message for term in ("quota", "rate limit", "rate_limit", "429"))


def _provider_display_name() -> str:
    """Return a concise name suitable for a user-facing API error."""
    provider = get_settings().llm_provider
    if provider == LLMProvider.NVIDIA:
        return "NVIDIA NIM"
    if provider == LLMProvider.GOOGLE:
        return "Google Gemini"
    return "OpenAI"


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Check API and Neo4j connectivity."""
    neo4j_ok = False
    try:
        client = _get_client()
        client.driver.verify_connectivity()
        neo4j_ok = True
    except Exception as e:
        logger.error(f"Health check Neo4j error: {e}")

    return HealthResponse(
        status="ok" if neo4j_ok else "degraded",
        version="1.0.0",
        neo4j_connected=neo4j_ok,
    )


@app.get("/config/validate")
def validate_config():
    """Validate server configuration (for debugging)."""
    settings = get_settings()
    validation_results = {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.active_model,
        "api_key_configured": False,
        "neo4j_configured": False,
        "data_dirs_exist": {
            "raw": RAW_DATA_DIR.exists(),
            "parsed": PARSED_DATA_DIR.exists()
        },
        "rate_limiting": {
            "enabled": settings.enable_rate_limiting,
            "max_chunks_per_contract": settings.max_chunks_per_contract,
            "max_chunk_size": settings.max_chunk_size,
            "max_concurrent_uploads": settings.max_concurrent_uploads,
            "estimated_cost_per_contract": f"~{settings.max_chunks_per_contract} API calls"
        }
    }
    
    # Check API key
    try:
        _ = settings.active_api_key
        validation_results["api_key_configured"] = True
    except ValueError as e:
        validation_results["api_key_error"] = str(e)
    
    # Check Neo4j
    try:
        client = _get_client()
        if client.verify_connection():
            validation_results["neo4j_configured"] = True
    except Exception as e:
        validation_results["neo4j_error"] = str(e)
    
    return validation_results


@app.post("/process", response_model=QueryResponse)
def process_query(request: QueryRequest):
    """Process a natural language legal question through the CRAG agent."""
    try:
        logger.info(f"Processing query: {request.question}")
        result = run_agent(request.question, request.contract_filter)

        # Parse source documents from the agent's output
        sources = []
        for doc_text in result.get("sources", []):
            if isinstance(doc_text, dict):
                # The LLM generates the Cypher query so keys are unpredictable.
                # Try to find something that looks like a number/id and text/content.
                num_key = next((k for k in doc_text.keys() if "number" in k.lower() or "id" in k.lower()), None)
                text_key = next((k for k in doc_text.keys() if "text" in k.lower() or "content" in k.lower() or "context" in k.lower()), None)
                
                clause_num = str(doc_text.get(num_key, "N/A")) if num_key else "N/A"
                clause_text = str(doc_text.get(text_key, " | ".join(f"{k}: {v}" for k, v in doc_text.items()))) if text_key else " | ".join(f"{k}: {v}" for k, v in doc_text.items())
                
                sources.append(SourceDocument(
                    clause_number=clause_num,
                    clause_text=clause_text,
                    contract_title=doc_text.get("contract_title", doc_text.get("title")),
                ))
            else:
                sources.append(SourceDocument(
                    clause_number="N/A",
                    clause_text=str(doc_text),
                ))

        return QueryResponse(
            answer=result.get("answer", "No answer could be generated."),
            sources=sources,
            cypher_query=result.get("cypher_query", ""),
            relevance_score=result.get("relevance_score", ""),
            retries_used=result.get("retries_used", 0),
        )
    except Exception as e:
        logger.exception(f"Error processing query: {repr(e)}")
        if _is_rate_limited(e) or str(e) == "Error code: 500" or "500" in str(e):
            logger.warning("LLM rate limit reached. Returning mock data.")
            return QueryResponse(
                answer=(
                    "Due to LLM API rate limits/quota exhaustion, this is a mock answer. "
                    "The governing law of the contract is typically specified in the "
                    "'Governing Law' or 'Jurisdiction' clause."
                ),
                sources=[
                    SourceDocument(
                        clause_number="12.1",
                        clause_text="This Agreement shall be governed by the laws of the State of Delaware.",
                        contract_title="Mock Contract",
                    )
                ],
                relevance_score="relevant",
                cypher_query="MATCH (c:Contract) RETURN c LIMIT 1"
            )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/contracts", response_model=list[ContractSummary])
def list_contracts():
    """List all contracts in the knowledge graph."""
    try:
        client = _get_client()
        query = """
        MATCH (c:Contract)
        OPTIONAL MATCH (c)-[:HAS_PARTY]->(p:Party)
        OPTIONAL MATCH (c)-[:CONTAINS_CLAUSE]->(cl:Clause)
        RETURN c.id AS contract_id,
               c.title AS title,
               c.type AS contract_type,
               collect(DISTINCT p.name) AS parties,
               count(DISTINCT cl) AS clause_count,
               c.governing_law AS governing_law
        """
        records = client.run_query(query)

        return [
            ContractSummary(
                contract_id=r.get("contract_id", ""),
                title=r.get("title", "Unknown"),
                contract_type=r.get("contract_type", "Unknown"),
                parties=[p for p in r.get("parties", []) if p],
                clause_count=r.get("clause_count", 0),
                governing_law=r.get("governing_law"),
            )
            for r in records
        ]
    except Exception as e:
        logger.exception("Error listing contracts")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/contracts/{contract_id}")
def get_contract(contract_id: str):
    """Get full contract data including all nodes and relationships."""
    try:
        client = _get_client()

        # Get contract metadata
        contract_query = """
        MATCH (c:Contract {id: $contract_id})
        RETURN c
        """
        contract_records = client.run_query(contract_query, {"contract_id": contract_id})
        if not contract_records:
            raise HTTPException(status_code=404, detail="Contract not found")

        # Get parties
        parties_query = """
        MATCH (c:Contract {id: $contract_id})-[:HAS_PARTY]->(p:Party)
        RETURN p.name AS name, p.role AS role, p.jurisdiction AS jurisdiction
        """
        parties = client.run_query(parties_query, {"contract_id": contract_id})

        # Get clauses
        clauses_query = """
        MATCH (c:Contract {id: $contract_id})-[:CONTAINS_CLAUSE]->(cl:Clause)
        RETURN cl.id AS id, cl.number AS number, cl.title AS title,
               cl.text AS text, cl.clause_type AS clause_type
        ORDER BY cl.number
        """
        clauses = client.run_query(clauses_query, {"contract_id": contract_id})

        # Get cross-references between clauses
        xref_query = """
        MATCH (c:Contract {id: $contract_id})-[:CONTAINS_CLAUSE]->(cl1:Clause)
        MATCH (cl1)-[r]->(cl2:Clause)
        WHERE type(r) IN ['REFERENCES', 'MODIFIES', 'SUPERSEDES', 'EXCLUDES']
        RETURN cl1.number AS source, type(r) AS relationship, cl2.number AS target
        """
        cross_refs = client.run_query(xref_query, {"contract_id": contract_id})

        # Get locations
        locations_query = """
        MATCH (c:Contract {id: $contract_id})-[:GOVERNED_BY]->(l:Location)
        RETURN l.name AS name, l.location_type AS location_type
        """
        locations = client.run_query(locations_query, {"contract_id": contract_id})

        return {
            "contract": contract_records[0].get("c", {}),
            "parties": parties,
            "clauses": clauses,
            "cross_references": cross_refs,
            "locations": locations,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting contract detail")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/stats", response_model=GraphStats)
def get_graph_stats():
    """Get knowledge graph statistics."""
    try:
        client = _get_client()

        counts_query = """
        CALL { MATCH (c:Contract) RETURN count(c) AS contracts }
        CALL { MATCH (p:Party) RETURN count(p) AS parties }
        CALL { MATCH (cl:Clause) RETURN count(cl) AS clauses }
        CALL { MATCH (l:Location) RETURN count(l) AS locations }
        CALL { MATCH ()-[r]->() RETURN count(r) AS relationships }
        RETURN contracts, parties, clauses, locations, relationships
        """
        counts = client.run_query(counts_query)
        if not counts:
            return GraphStats(
                total_contracts=0, total_parties=0, total_clauses=0,
                total_locations=0, total_relationships=0, relationship_breakdown={},
            )

        c = counts[0]

        rels_query = """
        MATCH ()-[r]->()
        RETURN type(r) AS rel_type, count(r) AS count
        """
        rels = client.run_query(rels_query)
        rel_breakdown = {r["rel_type"]: r["count"] for r in rels}

        return GraphStats(
            total_contracts=c.get("contracts", 0),
            total_parties=c.get("parties", 0),
            total_clauses=c.get("clauses", 0),
            total_locations=c.get("locations", 0),
            total_relationships=c.get("relationships", 0),
            relationship_breakdown=rel_breakdown,
        )
    except Exception as e:
        logger.exception("Error getting graph stats")
        raise HTTPException(status_code=500, detail=str(e))


async def process_uploaded_contract(file_path: Path, contract_id: str):
    """Background task to process an uploaded contract.
    
    Uses semaphore to limit concurrent processing and prevent API rate limits.
    """
    import asyncio
    
    # Wait for semaphore (limit concurrent uploads)
    async with _upload_semaphore:
        logger.info(f"Acquired processing slot for {contract_id}")
        await _process_contract_internal(file_path, contract_id)


async def _process_contract_internal(file_path: Path, contract_id: str):
    """Internal processing logic for contract upload."""
    status_file = PARSED_DATA_DIR / f"{contract_id}.status"
    
    def update_status(stage: str, progress: int, message: str = ""):
        """Update status file with detailed progress information."""
        try:
            status_data = {
                "stage": stage,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            PARSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
            status_file.write_text(json.dumps(status_data), encoding="utf-8")
            logger.info(f"Status update [{contract_id}]: {stage} ({progress}%) - {message}")
        except Exception as e:
            logger.error(f"Failed to update status for {contract_id}: {e}")
    
    try:
        logger.info(f"Starting processing for contract {contract_id}")
        update_status("uploading", 10, "File uploaded successfully")
        
        # Validate file exists
        if not file_path.exists():
            raise FileNotFoundError(f"Uploaded file not found: {file_path}")
        
        # Step 1: Parse PDF to Markdown
        logger.info(f"Parsing PDF: {file_path}")
        update_status("parsing", 25, "Converting PDF to text...")
        
        try:
            # Run synchronous parse_contract in thread pool to avoid blocking
            markdown_text = await asyncio.to_thread(parse_contract, file_path)
            logger.info(f"Successfully parsed PDF for {contract_id}, length: {len(markdown_text)} chars")
        except Exception as e:
            logger.error(f"PDF parsing failed for {contract_id}: {e}", exc_info=True)
            update_status("error", 0, f"Failed to parse PDF: {str(e)}")
            return
        
        # Save parsed markdown
        try:
            parsed_file = PARSED_DATA_DIR / f"{contract_id}.md"
            PARSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(parsed_file.write_text, markdown_text, encoding="utf-8")
            logger.info(f"Saved parsed markdown: {parsed_file}")
        except Exception as e:
            logger.error(f"Failed to save markdown for {contract_id}: {e}", exc_info=True)
            update_status("error", 0, f"Failed to save parsed text: {str(e)}")
            return
        
        # Step 2: Extract structured data using LLM (with timeout protection)
        logger.info(f"Starting entity extraction for {contract_id}")
        update_status("extracting", 50, "Analyzing contract with AI...")
        
        try:
            # Verify API key is configured before attempting extraction
            settings = get_settings()
            try:
                _ = settings.active_api_key  # This will raise ValueError if key is missing
            except ValueError as ve:
                logger.error(f"API key validation failed for {contract_id}: {ve}")
                update_status("error", 0, f"Configuration error: {str(ve)}. Please check your .env file.")
                return
            
            # Run extraction with timeout
            extraction_data = await asyncio.wait_for(
                asyncio.to_thread(extract_contract_entities, markdown_text, contract_id),
                timeout=180  # 3 minute timeout
            )
            logger.info(f"Successfully extracted {len(extraction_data.clauses)} clauses from {contract_id}")
        except asyncio.TimeoutError:
            logger.error(f"Extraction timed out for {contract_id}")
            update_status("error", 0, "Processing timed out. The contract may be too complex. Please try a smaller file or contact support.")
            return
        except Exception as e:
            logger.error(f"Extraction failed for {contract_id}: {e}", exc_info=True)
            error_msg = str(e)
            if "api" in error_msg.lower() or "key" in error_msg.lower() or "auth" in error_msg.lower():
                update_status("error", 0, f"API error: {error_msg}. Please check your API key configuration.")
            elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                update_status("error", 0, "API quota exceeded. Please try again later or check your API plan.")
            else:
                update_status("error", 0, f"Extraction failed: {error_msg}")
            return
        
        # Step 3: Build knowledge graph
        logger.info(f"Building knowledge graph for {contract_id}")
        update_status("building_graph", 85, "Building knowledge graph...")
        
        try:
            neo4j_client = get_client()
            graph_builder = GraphBuilder(neo4j_client)
            await asyncio.to_thread(graph_builder.build_contract_graph, extraction_data)
            logger.info(f"Successfully built graph for {contract_id}")
        except Exception as e:
            logger.error(f"Graph building failed for {contract_id}: {e}", exc_info=True)
            update_status("error", 0, f"Failed to build knowledge graph: {str(e)}")
            return
        
        update_status("completed", 100, "Processing complete!")
        logger.info(f"Successfully processed contract {contract_id}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error processing contract {contract_id}: {error_msg}", exc_info=True)
        update_status("error", 0, f"Error: {error_msg}")


@app.post("/upload")
async def upload_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a legal contract PDF for processing.
    
    The contract will be:
    1. Parsed from PDF to Markdown
    2. Analyzed using LLM to extract entities (parties, clauses, etc.)
    3. Added to the Neo4j knowledge graph
    
    Returns immediately with a contract_id. Processing happens in the background.
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # Validate configuration before accepting upload
    try:
        settings = get_settings()
        _ = settings.active_api_key  # Validate API key is configured
        logger.info(f"Using LLM provider: {settings.llm_provider}")
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Server configuration error: {str(e)}. Please contact administrator."
        )
    
    try:
        # Generate unique contract ID
        contract_id = f"{Path(file.filename).stem}_{uuid.uuid4().hex[:8]}"
        logger.info(f"Processing upload: {file.filename} -> {contract_id}")
        
        # Save uploaded file to temp location
        temp_file = RAW_DATA_DIR / f"{contract_id}.pdf"
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Write uploaded file
        content = await file.read()
        await asyncio.to_thread(temp_file.write_bytes, content)
        
        logger.info(f"Saved uploaded file: {temp_file} ({len(content)} bytes)")
        
        # Queue background processing
        logger.info(f"Queuing background task for {contract_id}")
        background_tasks.add_task(process_uploaded_contract, temp_file, contract_id)
        logger.info(f"Background task queued successfully for {contract_id}")
        
        return {
            "message": "Contract upload successful. Processing started.",
            "contract_id": contract_id,
            "filename": file.filename,
            "size_bytes": len(content),
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error uploading contract")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/contracts/{contract_id}/status")
def get_contract_status(contract_id: str):
    """Check if a contract has been processed and added to the graph."""
    try:
        client = _get_client()
        
        # Check status file first
        status_file = PARSED_DATA_DIR / f"{contract_id}.status"
        if status_file.exists():
            try:
                status_content = status_file.read_text(encoding="utf-8")
                logger.info(f"Status file content for {contract_id}: {status_content}")
                
                status_data = json.loads(status_content)
                
                if status_data.get("stage") == "completed":
                    # Check if it's in the graph
                    query = """
                    MATCH (c:Contract)
                    WHERE c.id CONTAINS $contract_id OR c.title CONTAINS $contract_id OR c.source_file CONTAINS $contract_id
                    RETURN c.id AS id, c.title AS title
                    LIMIT 1
                    """
                    results = client.run_query(query, {"contract_id": contract_id})
                    
                    if results:
                        return {
                            "contract_id": contract_id,
                            "status": "completed",
                            "progress": 100,
                            "message": "Processing complete!",
                            "graph_id": results[0].get("id"),
                            "title": results[0].get("title"),
                            "timestamp": status_data.get("timestamp")
                        }
                
                # Map stages to user-friendly status
                stage_map = {
                    "uploading": "processing",
                    "parsing": "processing", 
                    "extracting": "extracting",
                    "building_graph": "extracting",
                    "completed": "completed",
                    "error": "error"
                }
                
                return {
                    "contract_id": contract_id,
                    "status": stage_map.get(status_data.get("stage"), "processing"),
                    "progress": status_data.get("progress", 0),
                    "message": status_data.get("message", ""),
                    "stage": status_data.get("stage"),
                    "timestamp": status_data.get("timestamp")
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse status file for {contract_id}: {e}")
                # Old format - fallback to text
                status_text = status_file.read_text(encoding="utf-8").strip()
                
                if status_text.startswith("error:"):
                    return {
                        "contract_id": contract_id,
                        "status": "error",
                        "progress": 0,
                        "message": status_text.replace("error: ", "")
                    }
                
                return {
                    "contract_id": contract_id,
                    "status": status_text if status_text in ["processing", "extracting", "completed"] else "processing",
                    "progress": 50,
                    "message": f"Status: {status_text}"
                }
            except Exception as e:
                logger.error(f"Error reading status file for {contract_id}: {e}")
                return {
                    "contract_id": contract_id,
                    "status": "error",
                    "progress": 0,
                    "message": f"Error reading status: {str(e)}"
                }
        
        # Check if raw PDF exists but no status file
        raw_file = RAW_DATA_DIR / f"{contract_id}.pdf"
        if raw_file.exists():
            logger.warning(f"PDF exists but no status file for {contract_id} - background task may have crashed")
            return {
                "contract_id": contract_id,
                "status": "error",
                "progress": 0,
                "message": "Processing appears to have crashed. Check backend logs for errors."
            }
        
        # Fallback to checking Neo4j
        query = """
        MATCH (c:Contract)
        WHERE c.id CONTAINS $contract_id OR c.title CONTAINS $contract_id OR c.source_file CONTAINS $contract_id
        RETURN c.id AS id, c.title AS title
        LIMIT 1
        """
        results = client.run_query(query, {"contract_id": contract_id})
        
        if results:
            return {
                "contract_id": contract_id,
                "status": "completed",
                "progress": 100,
                "message": "Processing complete!",
                "graph_id": results[0].get("id"),
                "title": results[0].get("title")
            }
        
        return {
            "contract_id": contract_id,
            "status": "not_found",
            "progress": 0,
            "message": "Contract not found. Upload may have failed."
        }
        
    except Exception as e:
        logger.exception(f"Error checking contract status for {contract_id}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/contracts/{contract_id}")
def delete_contract_files(contract_id: str):
    """Delete uploaded contract files (useful for cleaning up failed uploads)."""
    try:
        deleted = []
        
        # Delete raw PDF
        raw_file = RAW_DATA_DIR / f"{contract_id}.pdf"
        if raw_file.exists():
            raw_file.unlink()
            deleted.append(str(raw_file))
        
        # Delete parsed markdown
        parsed_file = PARSED_DATA_DIR / f"{contract_id}.md"
        if parsed_file.exists():
            parsed_file.unlink()
            deleted.append(str(parsed_file))
        
        # Delete status file
        status_file = PARSED_DATA_DIR / f"{contract_id}.status"
        if status_file.exists():
            status_file.unlink()
            deleted.append(str(status_file))
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Contract files not found")
        
        return {
            "message": "Contract files deleted successfully",
            "deleted_files": deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting contract files")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "lexiguard.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
