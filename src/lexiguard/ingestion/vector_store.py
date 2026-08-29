import logging
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from lexiguard.config import LLMProvider, get_settings, CHROMA_DATA_DIR

logger = logging.getLogger(__name__)

def get_embeddings():
    """Return the configured LangChain Embeddings based on application settings."""
    settings = get_settings()

    if settings.llm_provider == LLMProvider.OPENAI:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small"
        )
    elif settings.llm_provider == LLMProvider.GOOGLE:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            api_key=settings.google_api_key,
            model="models/embedding-001"
        )
    elif settings.llm_provider == LLMProvider.NVIDIA:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model="nvidia/nv-embedqa-e5-v5"
        )
    else:
        raise ValueError(f"Unsupported LLM provider for embeddings: {settings.llm_provider}")

def get_vectorstore():
    """Get or create the ChromaDB vector store."""
    CHROMA_DATA_DIR.mkdir(parents=True, exist_ok=True)
    embeddings = get_embeddings()
    return Chroma(
        collection_name="contracts",
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DATA_DIR)
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
        
    metadatas = [{"contract_id": contract_id, "chunk_index": i} for i in range(len(chunks))]
    
    vectorstore = get_vectorstore()
    vectorstore.add_texts(texts=chunks, metadatas=metadatas)
    
    logger.info(f"Successfully stored {len(chunks)} semantic chunks for {contract_id} in ChromaDB")
