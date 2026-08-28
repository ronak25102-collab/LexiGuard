import logging
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from lexiguard.config import LLMProvider, PROJECT_ROOT, get_settings
from lexiguard.graph.schema import ContractData, ExtractionData

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CUAD_CATEGORIES = [
    "Document Name", "Parties", "Agreement Date", "Effective Date", "Expiration Date",
    "Renewal Term", "Notice Period To Terminate Renewal", "Governing Law",
    "Most Favored Nation", "Non-Compete", "Exclusivity", "No-Solicit Of Customers",
    "Competitive Restriction Exception", "No-Solicit Of Employees",
    "Non-Disparagement", "Termination For Convenience", "Rofr/Rofo/Rofn",
    "Change Of Control", "Anti-Assignment", "Revenue/Profit Sharing",
    "Price Restriction", "Volume Restriction", "Ip Ownership Assignment",
    "Joint Ip Ownership", "License Grant", "Non-Transferable License",
    "Affiliate License-Licensor", "Affiliate License-Licensee",
    "Unlimited/All-You-Can-Eat-License", "Irrevocable Or Perpetual License",
    "Source Code Escrow", "Post-Termination Services", "Audit Rights",
    "Uncapped Liability", "Cap On Liability", "Liquidated Damages",
    "Warranty Duration", "Insurance", "Covenant Not To Sue", "Third Party Beneficiary"
]


def _extract_with_openai(text_chunk: str, prompt: str) -> ExtractionData:
    """Extract structured data using OpenAI via instructor."""
    import instructor
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    patched_client = instructor.from_openai(client)

    response = patched_client.chat.completions.create(
        response_model=ExtractionData,
        model=settings.openai_model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text_chunk}
        ]
    )
    return response


def _extract_with_nvidia(text_chunk: str, prompt: str) -> ExtractionData:
    """Extract structured data using NVIDIA NIM's OpenAI-compatible API."""
    import instructor
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
    )
    patched_client = instructor.from_openai(client)

    response = patched_client.chat.completions.create(
        response_model=ExtractionData,
        model=settings.nvidia_model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text_chunk},
        ],
    )
    return response


def _extract_with_google(text_chunk: str, prompt: str) -> ExtractionData:
    """Extract structured data using Google Gemini via LangChain's with_structured_output."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model=settings.google_model,
        api_key=settings.google_api_key,
        temperature=0.0,
        timeout=60,  # 60 second timeout
        max_retries=1,  # Reduce retries within the LLM client
    )

    structured_llm = llm.with_structured_output(ExtractionData)
    full_prompt = f"{prompt}\n\n{text_chunk}"
    response = structured_llm.invoke(full_prompt)
    return response


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
def _extract_chunk(text_chunk: str, prompt: str) -> ExtractionData:
    """Extract structured data from a chunk of text using the configured LLM."""
    settings = get_settings()
    try:
        if settings.llm_provider == LLMProvider.OPENAI:
            return _extract_with_openai(text_chunk, prompt)
        if settings.llm_provider == LLMProvider.GOOGLE:
            return _extract_with_google(text_chunk, prompt)
        if settings.llm_provider == LLMProvider.NVIDIA:
            return _extract_with_nvidia(text_chunk, prompt)
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
    except Exception as e:
        logger.warning(f"Extraction failed, retrying: {e}")
        raise


def chunk_markdown(markdown_text: str, max_chars: int = 25000, max_chunks: int | None = None) -> list[str]:
    """Split markdown into chunks based on headers. Increased size for fewer API calls.
    
    Args:
        markdown_text: The markdown text to chunk
        max_chars: Maximum characters per chunk
        max_chunks: Maximum number of chunks to return (for cost control)
    
    Returns:
        List of text chunks, limited by max_chunks if specified
    """
    chunks = []
    lines = markdown_text.split('\n')
    current_chunk = []
    current_length = 0

    for line in lines:
        if line.startswith('#') and current_length > max_chars:
            chunks.append('\n'.join(current_chunk))
            current_chunk = []
            current_length = 0
            
            # Stop if we've reached max chunks
            if max_chunks and len(chunks) >= max_chunks:
                logger.warning(f"Reached max_chunks limit ({max_chunks}). Remaining text will be truncated.")
                break

        current_chunk.append(line)
        current_length += len(line) + 1

    # Add final chunk if we haven't hit the limit
    if current_chunk and (not max_chunks or len(chunks) < max_chunks):
        chunks.append('\n'.join(current_chunk))

    return chunks


def extract_contract_entities(markdown_text: str, filename: str) -> ContractData:
    """Extract structured legal entities from parsed markdown using LLM.
    
    Note: This function respects max_chunks_per_contract setting to limit API usage.
    """
    settings = get_settings()
    
    system_prompt = f"""
    You are a legal AI assistant. Extract key information from this contract.
    
    Focus on:
    - Contract title and type
    - Parties (name, role, jurisdiction)
    - Key clauses (number, title, text, type)
    - Important dates and governing law
    - Locations mentioned
    
    Filename: {filename}
    
    Extract the most important elements. Be concise.
    """

    # Apply rate limiting settings
    max_chunks = settings.max_chunks_per_contract if settings.enable_rate_limiting else None
    chunks = chunk_markdown(
        markdown_text, 
        max_chars=settings.max_chunk_size,
        max_chunks=max_chunks
    )
    
    extracted_data: list[ExtractionData] = []

    logger.info(f"Extracting entities from {filename} in {len(chunks)} chunks (limit: {max_chunks or 'unlimited'})")
    
    if len(chunks) > (max_chunks or 999):
        logger.warning(
            f"Contract chunked into {len(chunks)} parts, but only processing first {max_chunks} "
            f"due to rate limiting. Increase MAX_CHUNKS_PER_CONTRACT in .env if needed."
        )

    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
        try:
            chunk_data = _extract_chunk(chunk, system_prompt)
            extracted_data.append(chunk_data)
        except Exception as e:
            logger.error(f"Failed to extract from chunk {i+1}: {e}")
            # Continue with other chunks even if one fails

    if not extracted_data:
        raise RuntimeError("Failed to extract data from all chunks")

    # Merge chunks
    merged = extracted_data[0]
    for data in extracted_data[1:]:
        if data.title and not merged.title:
            merged.title = data.title
        if data.contract_type and not merged.contract_type:
            merged.contract_type = data.contract_type
        if data.effective_date and not merged.effective_date:
            merged.effective_date = data.effective_date
        if data.expiry_date and not merged.expiry_date:
            merged.expiry_date = data.expiry_date
        if data.governing_law and not merged.governing_law:
            merged.governing_law = data.governing_law
        merged.parties.extend(data.parties)
        merged.clauses.extend(data.clauses)
        merged.locations.extend(data.locations)
        merged.cross_references.extend(data.cross_references)

    # Simple deduplication by party name
    seen_parties = set()
    unique_parties = []
    for p in merged.parties:
        if p.name not in seen_parties:
            unique_parties.append(p)
            seen_parties.add(p.name)
    merged.parties = unique_parties

    # Convert ExtractionData to ContractData (adding source_file)
    return ContractData(
        source_file=filename,
        title=merged.title or filename,
        contract_type=merged.contract_type or "Unknown",
        effective_date=merged.effective_date,
        expiry_date=merged.expiry_date,
        governing_law=merged.governing_law,
        parties=merged.parties,
        clauses=merged.clauses,
        locations=merged.locations,
        cross_references=merged.cross_references,
    )


def extract_all_contracts(parsed_dir: Path = None) -> list[ContractData]:
    """Process all markdown files in the directory."""
    in_dir = parsed_dir or PROJECT_ROOT / "data" / "parsed"

    if not in_dir.exists():
        logger.warning(f"Parsed directory does not exist: {in_dir}")
        return []

    results = []
    for md_path in in_dir.glob("*.md"):
        logger.info(f"Extracting from {md_path.name}...")
        try:
            with open(md_path, encoding='utf-8') as f:
                content = f.read()

            data = extract_contract_entities(content, md_path.name)
            results.append(data)
            logger.info(f"Successfully extracted {len(data.clauses)} clauses from {md_path.name}")
        except Exception as e:
            logger.error(f"Error processing {md_path.name}: {e}")

    return results

if __name__ == "__main__":
    extract_all_contracts()
