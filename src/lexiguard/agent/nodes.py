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

        return ChatGoogleGenerativeAI(
            temperature=0,
            model=settings.google_model,
            api_key=settings.google_api_key,
        )
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


def retrieve(state: GraphState) -> dict[str, Any]:
    """Generate Cypher query from the question and retrieve context from Neo4j.

    This node:
    1. Sends the user's question to the LLM with the Cypher generation prompt
    2. Executes the generated Cypher query against Neo4j
    3. Returns the retrieved graph data as context
    """
    logger.info("Node: retrieve — Generating Cypher and querying graph")
    question = state["question"]
    contract_filter = state.get("contract_filter")

    llm = get_llm()

    # Build the prompt with optional contract filter
    prompt_text = CYPHER_GENERATION_PROMPT
    if contract_filter:
        prompt_text += f"\n\nIMPORTANT: Filter results for contract title or ID: {contract_filter}"

    cypher_query = ""
    try:
        response = llm.invoke(f"{prompt_text}\n\nQuestion: {question}")
        cypher_query = _get_text(response)

        # Clean up: remove markdown code fences if the LLM wraps the query
        if cypher_query.startswith("```"):
            lines = cypher_query.split("\n")
            cypher_query = "\n".join(
                line for line in lines if not line.strip().startswith("```")
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
                context_list.append(record_str)
                doc_list.append(dict(record))

        logger.info(f"Retrieved {len(context_list)} results from Neo4j")

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

    # Parse the response — look for clear "relevant" without "irrelevant"
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
    logger.info("Node: generate — Producing grounded answer")
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
    logger.info("Node: rewrite_query — Reformulating question for better retrieval")
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
    logger.info("Node: generate_with_disclaimer — Producing fallback answer")
    question = state["question"]
    context = "\n".join(state.get("graph_context", []))

    llm = get_llm()
    prompt = DISCLAIMER_PROMPT.format(question=question, context=context)

    response = llm.invoke(prompt)
    return {"generation": _get_text(response)}
