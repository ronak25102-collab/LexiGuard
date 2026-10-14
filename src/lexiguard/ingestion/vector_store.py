import logging
import hashlib
import math
from langchain_core.embeddings import Embeddings

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from lexiguard.config import LLMProvider, get_settings, CHROMA_DATA_DIR

logger = logging.getLogger(__name__)


class NormalizedEmbeddings(Embeddings):
    """Reduced-dimensional Gemini vectors need unit length for the indexed space."""

    def __init__(self, underlying: Embeddings):
        self.underlying = underlying

    @staticmethod
    def _unit(vector):
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._unit(v) for v in self.underlying.embed_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self._unit(self.underlying.embed_query(text))

def get_embeddings():
    """Return the configured LangChain Embeddings based on application settings."""
    settings = get_settings()
    provider = settings.effective_embedding_provider

    if provider == LLMProvider.OPENAI:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small"
        )
    elif provider == LLMProvider.GOOGLE:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return NormalizedEmbeddings(GoogleGenerativeAIEmbeddings(
            api_key=settings.google_api_key,
            model="models/gemini-embedding-001",
            output_dimensionality=768,
        ))
    elif provider == LLMProvider.NVIDIA:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model="nvidia/nv-embedqa-e5-v5"
        )
    else:
        raise ValueError(f"Unsupported provider for embeddings: {provider}")

def get_vectorstore():
    """Get or create the ChromaDB vector store."""
    CHROMA_DATA_DIR.mkdir(parents=True, exist_ok=True)
    embeddings = get_embeddings()
    google = get_settings().effective_embedding_provider == LLMProvider.GOOGLE
    directory = CHROMA_DATA_DIR / "gemini_embedding_001_768" if google else CHROMA_DATA_DIR
    return Chroma(
        # A model-specific collection avoids mixing old Google embeddings with the new model.
        collection_name=("contracts_gemini_embedding_001_768" if google else "contracts"),
        embedding_function=embeddings,
        persist_directory=str(directory)
    )

def add_contract_to_vectorstore(contract_id: str, markdown_text: str):
    """Process raw markdown text, split into chunks, and store in ChromaDB."""
    logger.info(f"Generating semantic embeddings for contract {contract_id}")
    
    # Semantic chunking strategy
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=200,
        length_function=len,
    )
    
    chunks = text_splitter.split_text(markdown_text)
    
    if not chunks:
        logger.warning(f"No text extracted for contract {contract_id}")
        return
        
    title = next((line.lstrip('# ').strip() for line in markdown_text.splitlines()
                  if line.startswith('#')), contract_id)
    canonical_id = hashlib.sha256(contract_id.encode()).hexdigest()
    metadatas = [{"contract_id": canonical_id, "source_file": contract_id,
                  "legacy_contract_id": contract_id, "contract_title": title,
                  "chunk_index": i} for i in range(len(chunks))]
    
    vectorstore = get_vectorstore()
    ids = [hashlib.sha256(f"{canonical_id}:{i}:{chunk}".encode()).hexdigest()
           for i, chunk in enumerate(chunks)]
    vectorstore.add_texts(texts=chunks, metadatas=metadatas, ids=ids)
    
    logger.info(f"Successfully stored {len(chunks)} semantic chunks for {contract_id} in ChromaDB")
