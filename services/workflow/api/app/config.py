from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@postgres:5432/docs_db"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5

    # LLM provider (OpenAI-compatible chat completions API)
    llm_provider: str = "meta"
    llm_base_url: str = "https://inference.do-ai.run/v1"
    llm_api_key: str = ""
    llm_model: str = "llama-4-maverick"
    llm_request_timeout: float = 120.0

    # Retrieval / prompt shaping
    max_docs_per_query: int = 3
    max_chars_per_doc: int = 6000
    max_total_context_chars: int = 12000

    # App
    app_name: str = "doc-chat-service"
    cors_allow_origins: str = "*"
    log_level: str = "INFO"

    # Only requests whose user_role equals this are processed; everything
    # else is rejected with 403 before any DB/LLM work happens.
    required_user_role: str = "agent"

    # Rate limiting (in-memory, per worker process — run with a single
    # uvicorn worker so limits are actually shared/consistent).
    rate_limit_per_minute: int = 30

    # Reject request bodies larger than this before touching the DB or LLM.
    max_request_body_bytes: int = 20_000


@lru_cache
def get_settings() -> Settings:
    return Settings()
