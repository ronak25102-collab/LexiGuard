import operator
from typing import Annotated, TypedDict


class GraphState(TypedDict):
    """
    State definition for the LexiGuard CRAG LangGraph agent.
    """
    question: str
    cypher_query: str
    graph_context: Annotated[list[str], operator.add]
    generation: str
    relevance_score: str
    retry_count: int
    documents: list[str]
    contract_filter: str | None
