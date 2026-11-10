"""Configuration module for LexiGuard.

Loads settings from environment variables / .env file using Pydantic Settings.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PARSED_DATA_DIR = DATA_DIR / "parsed"
CUAD_QA_DIR = DATA_DIR / "cuad_qa"
CHROMA_DATA_DIR = DATA_DIR / "chroma_db"


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = "openai"
    GOOGLE = "google"
    NVIDIA = "nvidia"
    CODECRAFT = "codecraft"
    NARAROUTER = "nararouter"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM Provider ---
    llm_provider: LLMProvider = LLMProvider.OPENAI
    embedding_provider: LLMProvider | None = None

    # OpenAI-compatible CodeCraft gateway; model identifiers are gateway-reported.
    codecraft_api_key: str | None = Field(default=None, repr=False)
    codecraft_api_keys: list[SecretStr] = Field(default_factory=list, repr=False)
    codecraft_model: str = "gpt-5.6-luna"
    codecraft_fallback_models: list[str] = Field(default_factory=list)
    codecraft_timeout: float = Field(default=30.0, gt=0)
    codecraft_max_tokens: int = Field(default=4096, gt=0)
    codecraft_base_url: str = "https://codecraftapi.com/v1"

    # OpenAI-compatible NaraRouter gateway (router.bynara.id)
    nararouter_api_key: str | None = Field(default=None, repr=False)
    nararouter_api_keys: list[SecretStr] = Field(default_factory=list, repr=False)
    nararouter_model: str = "gpt-6-luna"
    nararouter_fallback_models: list[str] = Field(default_factory=list)
    nararouter_timeout: float = Field(default=45.0, gt=0)
    nararouter_max_tokens: int = Field(default=4096, gt=0)
    nararouter_base_url: str = "https://router.bynara.id/v1"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Google Gemini
    google_api_key: str | None = None
    google_model: str = "gemini-3.5-flash"

    # NVIDIA NIM (OpenAI-compatible hosted API)
    nvidia_api_key: str | None = None
    nvidia_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_thinking: bool = False
    nvidia_reasoning_effort: str = "low"
    nvidia_max_tokens: int = 2048
    nvidia_timeout: float = 90.0
    nvidia_max_retries: int = 0

    # --- Neo4j ---
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_username: str = Field(default="neo4j")
    neo4j_password: str = Field(default="password")
    neo4j_ca_file: Path | None = None
    neo4j_connection_timeout: float = 15.0

    # --- LlamaCloud (optional) ---
    llama_cloud_api_key: str | None = None

    # --- Application ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    max_retries: int = 3
    agent_max_retries: int | None = None
    
    # --- Rate Limiting & Cost Control ---
    max_chunk_size: int = 30000  # Max characters per chunk
    max_chunks_per_contract: int = 3  # Limit chunks to save API calls
    max_concurrent_uploads: int = 2  # Max simultaneous processing
    enable_rate_limiting: bool = True  # Enable rate limiting

    @field_validator("llm_provider", "embedding_provider", mode="before")
    @classmethod
    def normalize_provider(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower().strip()
        return v

    @property
    def active_api_key(self) -> str:
        """Return the API key for the active LLM provider."""
        if self.llm_provider == LLMProvider.OPENAI:
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            return self.openai_api_key
        elif self.llm_provider == LLMProvider.GOOGLE:
            if not self.google_api_key:
                raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")
            return self.google_api_key
        elif self.llm_provider == LLMProvider.NVIDIA:
            if not self.nvidia_api_key:
                raise ValueError("NVIDIA_API_KEY is required when LLM_PROVIDER=nvidia")
            return self.nvidia_api_key
        elif self.llm_provider == LLMProvider.CODECRAFT:
            return self.codecraft_keys[0]
        elif self.llm_provider == LLMProvider.NARAROUTER:
            return self.nararouter_keys[0]
        raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    @property
    def nararouter_keys(self) -> list[str]:
        """Prefer an explicitly configured pool over the legacy single key."""
        keys = [key.get_secret_value().strip() for key in self.nararouter_api_keys]
        if not keys and self.nararouter_api_key:
            keys = [self.nararouter_api_key.strip()]
        keys = list(dict.fromkeys(key for key in keys if key))
        if not keys:
            raise ValueError("Set NARAROUTER_API_KEYS or NARAROUTER_API_KEY")
        return keys

    @property
    def codecraft_keys(self) -> list[str]:
        """Prefer an explicitly configured pool over the legacy single key."""
        keys = [key.get_secret_value().strip() for key in self.codecraft_api_keys]
        if not keys and self.codecraft_api_key:
            keys = [self.codecraft_api_key.strip()]
        keys = list(dict.fromkeys(key for key in keys if key))
        if not keys:
            raise ValueError("Set CODECRAFT_API_KEYS or CODECRAFT_API_KEY")
        return keys

    @property
    def active_model(self) -> str:
        """Return the model name for the active LLM provider."""
        if self.llm_provider == LLMProvider.OPENAI:
            return self.openai_model
        if self.llm_provider == LLMProvider.GOOGLE:
            return self.google_model
        if self.llm_provider == LLMProvider.NVIDIA:
            return self.nvidia_model
        if self.llm_provider == LLMProvider.CODECRAFT:
            return self.codecraft_model
        if self.llm_provider == LLMProvider.NARAROUTER:
            return self.nararouter_model
        raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    @property
    def effective_embedding_provider(self) -> LLMProvider:
        """Allow generation failover without silently changing the vector space."""
        provider = self.embedding_provider or self.llm_provider
        if provider in {LLMProvider.CODECRAFT, LLMProvider.NARAROUTER}:
            raise ValueError(f"Set EMBEDDING_PROVIDER explicitly when using {provider}")
        return provider

    def ensure_data_dirs(self) -> None:
        """Create data directories if they don't exist."""
        for d in [RAW_DATA_DIR, PARSED_DATA_DIR, CUAD_QA_DIR]:
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings singleton."""
    return Settings()
