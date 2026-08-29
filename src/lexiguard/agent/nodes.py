"""LangGraph node functions for the Corrective RAG pipeline.

Each function is a node in the LangGraph workflow that processes and updates
the shared GraphState.
"""

import logging
from typing import Any

from lexiguard.agent.prompts import (
    ANSWER_GENERATION_PROMPT,
    CYPHER_GENERATION_PROMPT,
    DISCLAIMER_PROMPT,
    QUERY_REWRITE_PROMPT,
    RELEVANCE_GRADING_PROMPT,
)
from lexiguard.agent.state import GraphState
from lexiguard.ingestion.vector_store import get_vectorstore

from lexiguard.config import LLMProvider, get_settings

logger = logging.getLogger(__name__)


def get_llm():
    """Return the configured LangChain LLM based on application settings."""
    settings = get_settings()

    if settings.llm_provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            temperature=0,
            model=settings.openai_model,
            api_key=settings.openai_api_key,
        )
    elif settings.llm_provider == LLMProvider.GOOGLE:
        from langchain_google_genai import ChatGoogleGenerativeAI

        primary_llm = ChatGoogleGenerativeAI(
            temperature=0,
            model=settings.google_model,
            api_key=settings.google_api_key,
        )
        
        fallback_llm = ChatGoogleGenerativeAI(
            temperature=0,
            model="gemini-3.5-flash-lite",
            api_key=settings.google_api_key,
        )
        
        return primary_llm.with_fallbacks([fallback_llm])
    elif settings.llm_provider == LLMProvider.NVIDIA:
        from langchain_openai import ChatOpenAI

        # NVIDIA NIM exposes an OpenAI-compatible chat-completions API.  Keep
        # model-specific chat-template settings in ``extra_body`` so they are
        # forwarded unchanged instead of being interpreted as OpenAI options.
        nvidia_options: dict[str, Any] = {
            "temperature": 0,
            "model": settings.nvidia_model,
            "api_key": settings.nvidia_api_key,
            "base_url": settings.nvidia_base_url,
            "max_tokens": settings.nvidia_max_tokens,
            "timeout": settings.nvidia_timeout,
            "max_retries": settings.nvidia_max_retries,
        }
        # These are DeepSeek-specific NIM parameters. Passing them to a
        # standard instruct model can make the provider reject the request.
        if settings.nvidia_model.startswith("deepseek-ai/"):
            nvidia_options["extra_body"] = {
                "chat_template_kwargs": {
                    "thinking": settings.nvidia_thinking,
                    "reasoning_effort": settings.nvidia_reasoning_effort,
                }
            }

        return ChatOpenAI(**nvidia_options)
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def _get_neo4j_client():
    """Get the Neo4j client singleton."""
    from lexiguard.graph.neo4j_client import get_client

    return get_client()


def _get_text(response) -> str:
    """Extract text from a LangChain response safely."""
    content = response.content
    if isinstance(content, list):
        return " ".join(item.get("text", "") for item in content if isinstance(item, dict)).strip()
    return str(content).strip()



def route_and_preprocess_query(state: GraphState) -> dict[str, Any]:
    """
    1. Classifies query intent: 'SUMMARY' vs 'SPECIFIC'.
    2. Extracts clean search entities (strips scenario numbers/conversational filler).
    """
    import json
    
    logger.info("Node: route_and_preprocess_query - Analyzing intent")
    llm = get_llm()
    question = state["question"]
    
    classification_prompt = f'''
    You are an intent classifier and query preprocessor for a Legal Contract Graph.
    
    Analyze the user question and return a JSON object with:
    1. "intent": "SUMMARY" (if asking for an overview, description, what it's about, or general greeting) 
                 OR "SPECIFIC" (if asking about penalties, clauses, rules, liabilities, specific scenarios).
    2. "extracted_parties": List of party/entity names mentioned (e.g., ["Nova", "Helios"]).
    3. "extracted_topics": List of core legal keywords (e.g., ["penalty", "delay", "software", "breach"]).
       CRITICAL: Strip conversational filler and specific scenario numbers (e.g., ignore '8,000' or 'quarter').
    
    User Question: "{question}"
    
    JSON Output:
    '''
    
    try:
        response = llm.invoke(classification_prompt)
        clean_json = _get_text(response).replace("`json", "").replace("`", "").strip()
        parsed = json.loads(clean_json)
        intent = parsed.get("intent", "SPECIFIC")
        search_terms = parsed.get("extracted_topics", []) + parsed.get("extracted_parties", [])
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        intent = "SPECIFIC"
        search_terms = [question]

    logger.info(f"Intent: {intent}, Search terms: {search_terms}")
    
    return {
        "intent": intent,
        "search_terms": search_terms,
    }

def retrieve(state: GraphState) -> dict[str, Any]:
    """Generate Cypher query, retrieve graph context, and query ChromaDB for semantic context.

    This node implements Hybrid Retrieval:
    1. Sends the user's question to the LLM with the Cypher generation prompt (Path A)
    2. Executes the generated Cypher query against Neo4j (Path A)
    3. Queries ChromaDB for semantic matches (Path B)
    4. Merges both into graph_context
    """
    logger.info("Node: retrieve - Generating Cypher and querying hybrid databases")
    question = state["question"]
    contract_filter = state.get("contract_filter")
    intent = state.get("intent", "SPECIFIC")
    search_terms = state.get("search_terms", [])

    if intent == "SUMMARY":
        logger.info("Handling SUMMARY query directly with Neo4j fast-track")
        client = _get_neo4j_client()
        query = '''
        MATCH (c:Contract)
        WHERE $contract_id IS NULL OR c.id = $contract_id OR toLower(c.title) CONTAINS toLower($contract_id)
        OPTIONAL MATCH (c)-[:HAS_PARTY]->(p:Party)
        OPTIONAL MATCH (c)-[:CONTAINS_CLAUSE]->(cl:Clause)
        RETURN c.title AS title, 
               c.contract_type AS type, 
               collect(DISTINCT p.name) AS parties, 
               collect(DISTINCT cl.title)[..8] AS key_sections
        LIMIT 1
        '''
        results = client.run_query(query, {"contract_id": contract_filter})
        
        context_list = []
        for record in results:
            summary_text = (
                f"Contract Title: {record.get('title')}\n"
                f"Type: {record.get('type')}\n"
                f"Parties Involved: {', '.join(record.get('parties', []))}\n"
                f"Key Sections: {', '.join(record.get('key_sections', []))}"
            )
            context_list.append(summary_text)
            
        return {
            "cypher_query": query,
            "graph_context": context_list,
            "documents": [],
        }

    llm = get_llm()

    # Build the prompt with optional contract filter
    prompt_text = CYPHER_GENERATION_PROMPT
    if contract_filter:
        prompt_text += f"\n\nIMPORTANT: Filter results for contract title or ID: {contract_filter}"
        
    if search_terms:
        prompt_text += f"\n\nExtracted Key Terms (use these for exact/fuzzy matching instead of raw scenario text): {', '.join(search_terms)}"
    cypher_query = ""
    try:
        # PATH A: Neo4j Structured Graph Retrieval
        response = llm.invoke(f"{prompt_text}\n\nQuestion: {question}")
        cypher_query = _get_text(response)

        # Clean up: remove markdown code fences if the LLM wraps the query
        if cypher_query.startswith("`"):
            lines = cypher_query.split("\n")
            cypher_query = "\n".join(
                line for line in lines if not line.strip().startswith("`")
            )

        logger.info(f"Generated Cypher: {cypher_query}")

        # Execute against Neo4j
        client = _get_neo4j_client()
        results = client.run_query(cypher_query)

        # Extract context from results
        context_list = []
        doc_list = []
        for record in results:
            # Convert each record to a readable string
            record_str = " | ".join(f"{k}: {v}" for k, v in record.items() if v)
            if record_str:
                context_list.append(f"[GRAPH] {record_str}")
                doc_list.append(dict(record))

        logger.info(f"Retrieved {len(context_list)} results from Neo4j")

        # PATH B: ChromaDB Semantic Vector Retrieval
        try:
            vectorstore = get_vectorstore()
            # For ChromaDB, filter syntax is metadata filtering
            search_kwargs = {"k": 3}
            # We don't have exact contract_id in filter sometimes (it might be title), 
            # so we just do a generic search if we aren't sure, but let's try.
            # We'll just do a standard similarity search without strict metadata filtering for now
            # to ensure we don't drop results due to ID mismatch.
            semantic_docs = vectorstore.similarity_search(" ".join(search_terms) if search_terms else question, **search_kwargs)
            logger.info(f"Retrieved {len(semantic_docs)} semantic results from ChromaDB")
            
            for doc in semantic_docs:
                context_list.append(f"[SEMANTIC] {doc.page_content}")
                doc_list.append({"type": "semantic_chunk", "content": doc.page_content, "metadata": doc.metadata})
        except Exception as ve:
            logger.error(f"Semantic retrieve error (ChromaDB): {ve}")

        return {
            "cypher_query": cypher_query,
            "graph_context": context_list,
            "documents": doc_list,
        }
    except Exception as e:
        logger.error(f"Retrieve error: {e}")
        return {
            "cypher_query": cypher_query,
            "graph_context": [],
            "documents": [],
        }


def grade_relevance(state: GraphState) -> dict[str, Any]:
    """Evaluate whether the retrieved graph context answers the user's question.

    This is the core "guardrail" node that prevents hallucination by checking
    if the retrieved data is actually relevant before generating an answer.
    """
    logger.info("Node: grade_relevance — Evaluating context quality")
    
    # --- Bypass CRAG auditor for general summaries ---
    if state.get("intent") == "SUMMARY":
        logger.info("SUMMARY intent detected — bypassing auditor check")
        return {"relevance_score": "relevant"}
    # ---------------------------------------------------
    
    question = state["question"]
    context = "\n".join(state.get("graph_context", []))

    # If no context was retrieved, it's automatically irrelevant
    if not context.strip():
        logger.info("No context retrieved — marking as irrelevant")
        return {"relevance_score": "irrelevant"}

    llm = get_llm()
    prompt = RELEVANCE_GRADING_PROMPT.format(question=question, context=context)

    response = llm.invoke(prompt)
    raw_score = _get_text(response).lower()

    # Parse the response Ã¢â‚¬â€ look for clear "relevant" without "irrelevant"
    if "relevant" in raw_score and "irrelevant" not in raw_score:
        score = "relevant"
    else:
        score = "irrelevant"

    logger.info(f"Relevance score: {score}")
    return {"relevance_score": score}


def generate(state: GraphState) -> dict[str, Any]:
    """Generate the final answer grounded in the verified graph context.

    Only called after the grade_relevance node has confirmed the context
    is relevant to the user's question.
    """
    logger.info("Node: generate Ã¢â‚¬â€ Producing grounded answer")
    question = state["question"]
    context = "\n".join(state.get("graph_context", []))

    llm = get_llm()
    prompt = ANSWER_GENERATION_PROMPT.format(question=question, context=context)

    response = llm.invoke(prompt)
    return {"generation": _get_text(response)}


def rewrite_query(state: GraphState) -> dict[str, Any]:
    """Reformulate the user's question to improve Cypher generation on retry.

    Increments the retry counter so the routing logic can enforce the max
    retry limit.
    """
    logger.info("Node: rewrite_query Ã¢â‚¬â€ Reformulating question for better retrieval")
    question = state["question"]
    retry_count = state.get("retry_count", 0) + 1

    llm = get_llm()
    prompt = QUERY_REWRITE_PROMPT.format(question=question)

    response = llm.invoke(prompt)
    new_question = _get_text(response)

    logger.info(f"Rewritten question (attempt {retry_count}): {new_question}")
    return {
        "question": new_question,
        "retry_count": retry_count,
    }


def generate_with_disclaimer(state: GraphState) -> dict[str, Any]:
    """Generate an answer with a verification disclaimer.

    Called when the maximum number of retrieval retries has been exhausted
    without finding sufficiently relevant context.
    """
    logger.info("Node: generate_with_disclaimer Ã¢â‚¬â€ Producing fallback answer")
    question = state["question"]
    context = "\n".join(state.get("graph_context", []))

    llm = get_llm()
    prompt = DISCLAIMER_PROMPT.format(question=question, context=context)

    response = llm.invoke(prompt)
    return {"generation": _get_text(response)}



