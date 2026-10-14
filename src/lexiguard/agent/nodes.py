"""LangGraph node functions for the Corrective RAG pipeline.

Each function is a node in the LangGraph workflow that processes and updates
the shared GraphState.
"""

import logging
from typing import Any

from lexiguard.agent.prompts import (
    ANSWER_GENERATION_PROMPT,
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
    elif settings.llm_provider == LLMProvider.CODECRAFT:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.codecraft_model, api_key=settings.codecraft_api_key,
                          base_url=settings.codecraft_base_url, temperature=0,
                          max_tokens=8192, timeout=90, max_retries=2)
    elif settings.llm_provider == LLMProvider.GOOGLE:
        from langchain_google_genai import ChatGoogleGenerativeAI

        primary_llm = ChatGoogleGenerativeAI(
            temperature=0,
            model=settings.google_model,
            api_key=settings.google_api_key,
            max_retries=0, # Instantly failover to lite model on rate limit
            timeout=45,
        )
        
        fallback_llm = ChatGoogleGenerativeAI(
            temperature=0,
            model="gemini-3.5-flash-lite",
            api_key=settings.google_api_key,
            max_retries=1,
            timeout=45,
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
        elif "nemotron-3-" in settings.nvidia_model:
            nvidia_options["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": settings.nvidia_thinking}
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
        roles = {"client", "vendor", "company", "developer", "ma", "affiliate", "network"}
        party_filter = [p for p in parsed.get("extracted_parties", [])
                        if isinstance(p, str) and p.strip() and p.strip().lower() not in roles]
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        intent = "SPECIFIC"
        search_terms = [question]
        party_filter = []

    logger.info(f"Intent: {intent}, Search terms: {search_terms}")
    
    return {
        "intent": intent,
        "search_terms": search_terms,
        "party_filter": party_filter,
    }


SCOPE_QUERY = """
MATCH (c:Contract)
WHERE $filter IS NULL OR c.id = $filter OR c.title = $filter OR c.source_file = $filter
OPTIONAL MATCH (c)-[:HAS_PARTY]->(p:Party)
WITH c, collect(DISTINCT p.name) AS parties
WHERE $filter IS NOT NULL OR size($party_names) = 0 OR
      any(wanted IN $party_names WHERE
          any(actual IN parties WHERE toLower(actual) CONTAINS toLower(wanted)))
RETURN c.id AS contract_id, c.title AS contract_title, c.source_file AS source_file,
       parties
"""

CLAUSE_QUERY = """
MATCH (c:Contract)-[:CONTAINS_CLAUSE]->(cl:Clause)
WHERE c.id IN $contract_ids
AND any(term IN $terms WHERE
    toLower(coalesce(cl.title, '')) CONTAINS term OR
    toLower(coalesce(cl.clause_type, '')) CONTAINS term OR
    toLower(coalesce(cl.text, '')) CONTAINS term)
RETURN c.id AS contract_id, cl.id AS id, cl.number AS section,
       cl.title AS title, cl.text AS text, cl.clause_type AS clause_type
ORDER BY cl.number
LIMIT 120
"""

LINK_QUERY = """
MATCH (seed:Clause)-[r]-(linked:Clause)
MATCH (c:Contract)-[:CONTAINS_CLAUSE]->(linked)
WHERE seed.id IN $seed_ids AND c.id IN $contract_ids
AND type(r) IN ['REFERENCES', 'MODIFIES', 'SUPERSEDES', 'EXCLUDES']
RETURN c.id AS contract_id, linked.id AS id, linked.number AS section,
       linked.title AS title, linked.text AS text, linked.clause_type AS clause_type,
       seed.number AS linked_to, type(r) AS relationship
LIMIT 60
"""


def _local_source_candidates(question, contract_filter, contracts, party_names=None):
    """Lexical fallback searches source text when vector indexing is unavailable."""
    import hashlib
    import json
    from lexiguard.config import PARSED_DATA_DIR, DATA_DIR
    from lexiguard.agent.retrieval import normalize, rank_candidates, source_aliases
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    metadata = {c.get("source_file"): c for c in contracts}
    extracted_path = DATA_DIR / "extracted_contracts.json"
    if extracted_path.exists():
        try:
            for c in json.loads(extracted_path.read_text("utf-8")):
                metadata.setdefault(c["source_file"], {
                    "contract_id": hashlib.sha256(c["source_file"].encode()).hexdigest(),
                    "contract_title": c["title"], "source_file": c["source_file"],
                    "parties": [p["name"] for p in c["parties"]],
                })
        except (ValueError, KeyError):
            logger.warning("Local extraction metadata could not be read")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    docs = []
    for path in sorted(PARSED_DATA_DIR.glob("*.md")):
        record = metadata.get(path.name) or metadata.get(path.stem) or {}
        content = path.read_text("utf-8")
        if not record:
            source = path.stem if path.with_suffix(".status").exists() else path.name
            title = next((line.lstrip("# ").strip() for line in content.splitlines()
                          if line.startswith("#")), path.stem)
            record = {"contract_id": hashlib.sha256(source.encode()).hexdigest(),
                      "contract_title": title, "source_file": source}
        if contract_filter and contract_filter not in source_aliases(record):
            if normalize(contract_filter) != normalize(record.get("contract_title", "")):
                continue
        if not contract_filter and party_names:
            parties_text = normalize(" ".join(record.get("parties", [])) or content[:2000])
            if not any(normalize(name) in parties_text for name in party_names):
                continue
        for chunk in splitter.split_text(content):
            docs.append({**record, "text": chunk, "kind": "lexical_source", "section": None})
    return rank_candidates(question, docs)[:12]


def retrieve(state: GraphState, *, use_graph: bool = True, use_links: bool = True) -> dict[str, Any]:
    """Retrieve scoped graph and semantic evidence independently, then fuse it."""
    from lexiguard.agent.retrieval import (
        rank_candidates, search_query, select_context, source_aliases, topic_terms,
    )

    original = state["question"]
    query = state.get("retrieval_question") or original
    contract_filter = state.get("contract_filter")
    party_names = state.get("party_filter", []) if not contract_filter else []
    contracts, graph_docs, semantic_docs, errors = [], [], [], []
    cypher = CLAUSE_QUERY.strip()
    try:
        client = _get_neo4j_client()
        contracts = client.run_query(SCOPE_QUERY, {"filter": contract_filter,
                                                  "party_names": party_names})
        ids = [c["contract_id"] for c in contracts]
        info = {c["contract_id"]: c for c in contracts}
        if ids and use_graph:
            rows = client.run_query(CLAUSE_QUERY, {"contract_ids": ids, "terms": topic_terms(query)})
            graph_docs = [{**info[r["contract_id"]], **r, "kind": "graph"}
                          for r in rows if r.get("text")]
            seeds = rank_candidates(original, graph_docs)[:2]
            if seeds and use_links:
                linked = client.run_query(
                    LINK_QUERY, {"seed_ids": [d["id"] for d in seeds], "contract_ids": ids}
                )
                graph_docs = seeds + [{**info[r["contract_id"]], **r, "kind": "graph"}
                                      for r in linked if r.get("text")] + graph_docs
    except Exception as error:
        logger.warning("Graph retrieval unavailable: %s", type(error).__name__)
        errors.append("graph_unavailable")

    # Graph errors must not discard successful semantic retrieval.
    try:
        vectorstore = get_vectorstore()
        kwargs = {"k": 8}
        if contract_filter or party_names:
            aliases = [alias for c in contracts for alias in source_aliases(c)]
            if not aliases:
                if party_names:
                    raise ValueError("Named-party scope could not be resolved")
                aliases = [contract_filter]
            kwargs["filter"] = {"contract_id": {"$in": list(dict.fromkeys(aliases))}}
        for doc in vectorstore.similarity_search(search_query(query), **kwargs):
            metadata = dict(doc.metadata)
            contract = next((c for c in contracts if metadata.get("contract_id")
                             in source_aliases(c)), {})
            semantic_docs.append({**metadata, **contract, "text": doc.page_content,
                                  "kind": "semantic", "section": None})
    except Exception as error:
        logger.warning("Semantic retrieval unavailable: %s", type(error).__name__)
        errors.append("semantic_unavailable")
    if not semantic_docs:
        semantic_docs = _local_source_candidates(query, contract_filter, contracts, party_names)
    selected = select_context(original, graph_docs, semantic_docs)
    return {"cypher_query": cypher, "graph_context": [d["text"] for d in selected],
            "documents": selected, "retrieval_errors": errors,
            "semantic_documents": select_context(original, [], semantic_docs)}


def grade_relevance(state: GraphState) -> dict[str, Any]:
    """Evaluate whether the retrieved graph context answers the user's question.

    This is the core "guardrail" node that prevents hallucination by checking
    if the retrieved data is actually relevant before generating an answer.
    """
    logger.info("Node: grade_relevance — Evaluating context quality")

    # Compare alternatives rather than judging only a possibly degraded fusion.
    if "semantic_documents" in state:
        import json
        from lexiguard.agent.prompts import EVIDENCE_SELECTION_PROMPT
        semantic = state["semantic_documents"]
        hybrid = state.get("documents", [])
        prompt = EVIDENCE_SELECTION_PROMPT.format(
            question=state["question"], semantic="\n".join(d["text"] for d in semantic),
            hybrid="\n".join(d["text"] for d in hybrid))
        response = _get_text(get_llm().invoke(prompt))
        try:
            value = json.loads(response.strip().removeprefix("```json").removeprefix("```")
                               .removesuffix("```").strip())
            choice = value["choice"]
            relevance = value["relevance"]
            if choice not in {"semantic", "hybrid"} or relevance not in {"relevant", "irrelevant"}:
                raise ValueError("Invalid evidence selection")
            selected = semantic if choice == "semantic" else hybrid
            return {"documents": selected, "graph_context": [d["text"] for d in selected],
                    "relevance_score": relevance if selected else "irrelevant",
                    "evidence_choice": choice, "evidence_reason": str(value.get("reason", ""))}
        except (KeyError, ValueError, TypeError):
            # Preserve the semantic alternative and retry, rather than accepting a bad fusion.
            return {"documents": semantic, "graph_context": [d["text"] for d in semantic],
                    "relevance_score": "irrelevant", "evidence_choice": "invalid_selection",
                    "evidence_reason": "Evidence selection could not be validated."}
    
    # --- Bypass CRAG auditor for general summaries ---
    if state.get("intent") == "SUMMARY" and state.get("graph_context"):
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
    question = state.get("retrieval_question") or state["question"]
    retry_count = state.get("retry_count", 0) + 1

    llm = get_llm()
    prompt = QUERY_REWRITE_PROMPT.format(question=question)

    response = llm.invoke(prompt)
    new_question = _get_text(response)

    logger.info(f"Rewritten question (attempt {retry_count}): {new_question}")
    return {
        "retrieval_question": new_question,
        "retry_count": retry_count,
    }


def generate_with_disclaimer(state: GraphState) -> dict[str, Any]:
    """Abstain when retrieval remains insufficient; never invent contractual silence."""
    return {"generation": "I could not retrieve enough evidence to answer this question reliably. "
            "Please review the source contract or try a more specific query."}
