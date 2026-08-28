
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for the /process endpoint."""
    question: str = Field(description="Natural language legal question")
    contract_filter: str | None = Field(default=None, description="Optional contract ID to scope the search")

class SourceDocument(BaseModel):
    """A source clause used to ground the answer."""
    clause_number: str
    clause_text: str
    contract_title: str | None = None

class QueryResponse(BaseModel):
    """Response model for the /process endpoint."""
    answer: str = Field(description="The generated legal answer")
    sources: list[SourceDocument] = Field(default_factory=list, description="Source clauses cited")
    cypher_query: str = Field(default="", description="The Cypher query that was executed")
    relevance_score: str = Field(default="", description="Relevance grading result")
    retries_used: int = Field(default=0, description="Number of CRAG retries")

class ContractSummary(BaseModel):
    """Summary of a contract in the knowledge graph."""
    contract_id: str
    title: str
    contract_type: str
    parties: list[str]
    clause_count: int
    governing_law: str | None = None

class GraphStats(BaseModel):
    """Statistics about the knowledge graph."""
    total_contracts: int
    total_parties: int
    total_clauses: int
    total_locations: int
    total_relationships: int
    relationship_breakdown: dict[str, int]

class HealthResponse(BaseModel):
    status: str
    version: str
    neo4j_connected: bool
