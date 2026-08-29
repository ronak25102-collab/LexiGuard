import json

file_path = "src/lexiguard/agent/nodes.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

new_node = """
def route_and_preprocess_query(state: GraphState) -> dict[str, Any]:
    \"\"\"
    1. Classifies query intent: 'SUMMARY' vs 'SPECIFIC'.
    2. Extracts clean search entities (strips scenario numbers/conversational filler).
    \"\"\"
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
        clean_json = _get_text(response).replace("```json", "").replace("```", "").strip()
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
        # Ensure we don't accidentally overwrite the question, but we provide search terms for retrieval
    }

def retrieve(state: GraphState) -> dict[str, Any]:
"""

content = content.replace("def retrieve(state: GraphState) -> dict[str, Any]:", new_node)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

