from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from lexiguard.agent.nodes import (
    generate,
    generate_with_disclaimer,
    grade_relevance,
    retrieve,
    route_and_preprocess_query,
    rewrite_query,
)
from lexiguard.agent.state import GraphState
from lexiguard.config import get_settings

# Global cached graph instance
_compiled_graph = None


def _is_party_question(question: str) -> bool:
    """Return whether the question can be answered safely without an LLM."""
    normalized = question.lower()
    return ("party" in normalized or "parties" in normalized) and any(
        phrase in normalized
        for phrase in ("who are", "who is", "involved", "contracting", "parties to")
    )


def _answer_party_question(contract_filter: str | None) -> dict:
    """Fetch named contract parties directly from the knowledge graph."""
    from lexiguard.graph.neo4j_client import get_client

    cypher_query = """
    MATCH (c:Contract)-[:HAS_PARTY]->(p:Party)
    WHERE $contract_filter IS NULL OR c.id = $contract_filter OR c.title = $contract_filter
    RETURN c.id AS contract_id,
           c.title AS contract_title,
           collect(DISTINCT p.name) AS parties
    ORDER BY contract_title
    """
    records = get_client().run_query(cypher_query, {"contract_filter": contract_filter})

    if not records:
        return {
            "answer": "No parties were found for the selected contract.",
            "sources": [],
            "cypher_query": cypher_query.strip(),
            "retries_used": 0,
            "relevance_score": "relevant",
        }

    answer_lines = ["The parties recorded in the knowledge graph are:"]
    sources = []
    for record in records:
        parties = [party for party in record.get("parties", []) if party]
        title = record.get("contract_title") or record.get("contract_id") or "Untitled contract"
        answer_lines.append(f"- {title}: {', '.join(parties) if parties else 'No named parties'}")
        sources.append(
            {
                "contract_title": title,
                "clause_number": "Parties",
                "clause_text": ", ".join(parties) if parties else "No named parties",
            }
        )

    return {
        "answer": "\n".join(answer_lines),
        "sources": sources,
        "cypher_query": cypher_query.strip(),
        "retries_used": 0,
        "relevance_score": "relevant",
    }

def route_after_grading(state: GraphState) -> str:
    """Determine the next node based on relevance grading."""
    score = state.get("relevance_score")
    retries = state.get("retry_count", 0)
    settings = get_settings()
    configured_retries = getattr(settings, "agent_max_retries", None)
    max_retries = configured_retries if isinstance(configured_retries, int) else settings.max_retries

    if score == "relevant":
        return "generate"
    elif score == "irrelevant" and retries < max_retries:
        return "rewrite_query"
    else:
        return "generate_with_disclaimer"

def build_graph() -> CompiledStateGraph:
    """Build and compile the LexiGuard CRAG workflow."""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("preprocess", route_and_preprocess_query)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("grade_relevance", grade_relevance)
    workflow.add_node("generate", generate)
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("generate_with_disclaimer", generate_with_disclaimer)

    # Add edges
    workflow.add_edge(START, "preprocess")
    workflow.add_edge("preprocess", "retrieve")
    workflow.add_edge("retrieve", "grade_relevance")

    workflow.add_conditional_edges(
        "grade_relevance",
        route_after_grading,
        {
            "generate": "generate",
            "rewrite_query": "rewrite_query",
            "generate_with_disclaimer": "generate_with_disclaimer"
        }
    )

    workflow.add_edge("rewrite_query", "retrieve")
    workflow.add_edge("generate", END)
    workflow.add_edge("generate_with_disclaimer", END)

    return workflow.compile()

def run_agent(question: str, contract_filter: str | None = None) -> dict:
    """Run the CRAG agent for a given legal question."""
    if _is_party_question(question):
        return _answer_party_question(contract_filter)

    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()

    initial_state = {
        "question": question,
        "contract_filter": contract_filter,
        "retry_count": 0,
        "cypher_query": "",
        "graph_context": [],
        "documents": [],
        "generation": "",
        "relevance_score": ""
    }

    final_state = _compiled_graph.invoke(initial_state)

    return {
        "answer": final_state.get("generation"),
        "sources": final_state.get("documents"),
        "cypher_query": final_state.get("cypher_query"),
        "retries_used": final_state.get("retry_count"),
        "relevance_score": final_state.get("relevance_score")
    }

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("Running sample query...")
    result = run_agent("What are the termination conditions for the vendor agreement?", "Vendor_Agr_001")
    print(f"Result: {result}")

