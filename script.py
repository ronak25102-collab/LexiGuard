import re

file_path = "src/lexiguard/ingestion/extractor.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace imports
content = content.replace("from lexiguard.graph.schema import ContractData, ExtractionData", 
"""from typing import TypeVar, Type
from pydantic import BaseModel
from lexiguard.graph.schema import ContractData, ExtractionData, PartyInfo

T = TypeVar('T', bound=BaseModel)

class PartyResolutionResult(BaseModel):
    \"\"\"Result of LLM-driven entity resolution.\"\"\"
    resolved_parties: list[PartyInfo]
""")

# Replace functions
content = content.replace("def _extract_with_openai(text_chunk: str, prompt: str) -> ExtractionData:", "def _extract_with_openai(text_chunk: str, prompt: str, model_class: Type[T] = ExtractionData) -> T:")
content = content.replace("response_model=ExtractionData,", "response_model=model_class,")

content = content.replace("def _extract_with_nvidia(text_chunk: str, prompt: str) -> ExtractionData:", "def _extract_with_nvidia(text_chunk: str, prompt: str, model_class: Type[T] = ExtractionData) -> T:")

content = content.replace("def _extract_with_google(text_chunk: str, prompt: str) -> ExtractionData:", "def _extract_with_google(text_chunk: str, prompt: str, model_class: Type[T] = ExtractionData) -> T:")
content = content.replace("structured_llm = llm.with_structured_output(ExtractionData)", "structured_llm = llm.with_structured_output(model_class)")

content = content.replace("def _extract_chunk(text_chunk: str, prompt: str) -> ExtractionData:", "def _extract_chunk(text_chunk: str, prompt: str, model_class: Type[T] = ExtractionData) -> T:")
content = content.replace("return _extract_with_openai(text_chunk, prompt)", "return _extract_with_openai(text_chunk, prompt, model_class)")
content = content.replace("return _extract_with_google(text_chunk, prompt)", "return _extract_with_google(text_chunk, prompt, model_class)")
content = content.replace("return _extract_with_nvidia(text_chunk, prompt)", "return _extract_with_nvidia(text_chunk, prompt, model_class)")

# Deduplication func
dedup_func = """

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
def _resolve_parties_with_llm(parties: list[PartyInfo]) -> list[PartyInfo]:
    \"\"\"Deduplicate aliases into unified primary entities.\"\"\"
    if not parties:
        return []
        
    logger.info(f"Running LLM entity resolution on {len(parties)} extracted parties...")
    
    prompt = '''
    You are an expert legal entity resolution engine.
    You will be given a list of extracted contracting parties. 
    In legal documents, the same company may be referred to by multiple aliases 
    (e.g., "Apex Enterprise Solutions, Inc.", "Apex", "The Client").
    
    Your job is to:
    1. Identify all aliases that refer to the exact same legal entity.
    2. Merge them into a SINGLE primary record per entity.
    3. Use the most formal name as the primary name.
    4. Keep the role (e.g., "Buyer", "Vendor"). If multiple roles exist, combine them or pick the most descriptive.
    
    Return ONLY the deduplicated, resolved list of primary parties.
    '''
    
    parties_text = "\\n".join([f"- Name: {p.name}, Role: {p.role}, Jurisdiction: {p.jurisdiction}" for p in parties])
    
    try:
        result = _extract_chunk(parties_text, prompt, PartyResolutionResult)
        logger.info(f"Entity resolution complete: Reduced {len(parties)} aliases to {len(result.resolved_parties)} unified entities.")
        return result.resolved_parties
    except Exception as e:
        logger.error(f"Entity resolution failed, falling back to naive deduplication: {e}")
        seen = set()
        unique = []
        for p in parties:
            if p.name not in seen:
                unique.append(p)
                seen.add(p.name)
        return unique
"""

# Replace naive logic
naive_logic = """    # Simple deduplication by party name
    seen_parties = set()
    unique_parties = []
    for p in merged.parties:
        if p.name not in seen_parties:
            unique_parties.append(p)
            seen_parties.add(p.name)
    merged.parties = unique_parties"""

content = content.replace(naive_logic, "    merged.parties = _resolve_parties_with_llm(merged.parties)")

# Append func at the bottom (but before extract_all_contracts if possible, or just append)
# Actually, appending at the bottom might put it after if __name__ == "__main__":
# Let's insert it before def extract_all_contracts

content = content.replace("def extract_all_contracts(parsed_dir: Path = None) -> list[ContractData]:", dedup_func + "\\ndef extract_all_contracts(parsed_dir: Path = None) -> list[ContractData]:")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

