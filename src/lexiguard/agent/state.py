from typing import NotRequired, TypedDict


class GraphState(TypedDict):
    """
    State definition for the LexiGuard CRAG LangGraph agent.
    """
    question: str
    retrieval_question: NotRequired[str]
    retrieval_errors: NotRequired[list[str]]
    party_filter: NotRequired[list[str]]
    cypher_query: str
    graph_context: list[str]
    generation: str
    relevance_score: str
    retry_count: int
    documents: list[dict]
    semantic_documents: NotRequired[list[dict]]
    evidence_choice: NotRequired[str]
    evidence_reason: NotRequired[str]
    contract_filter: str | None
    intent: str
    search_terms: list[str]
