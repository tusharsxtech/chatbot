"""Environment configuration for QueryWeaver."""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    pg_host: str = os.getenv("PGHOST", "localhost")
    pg_port: int = int(os.getenv("PGPORT", "5432"))
    pg_db: str = os.getenv("PGDATABASE", "kiotel")
    pg_user: str = os.getenv("PGUSER", "queryweaver_readonly")
    pg_password: str = os.getenv("PGPASSWORD", "")
    statement_timeout_ms: int = int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "5000"))
    default_row_limit: int = int(os.getenv("DEFAULT_ROW_LIMIT", "5"))

    llm_provider: str = os.getenv("LLM_PROVIDER", "meta")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "llama-4-maverick")

    # Hybrid (lexical + semantic) retrieval store: pgvector + Postgres
    # full-text search, combined via reciprocal rank fusion. Kept on a
    # separate database from the app's own business DB.
    vector_db_host: str = os.getenv("VECTOR_DB_HOST", "postgres")
    vector_db_port: int = int(os.getenv("VECTOR_DB_PORT", "5432"))
    vector_db_name: str = os.getenv("VECTOR_DB_NAME", "vanna_vectors")
    vector_db_user: str = os.getenv("VECTOR_DB_USER", "postgres")
    vector_db_password: str = os.getenv("VECTOR_DB_PASSWORD", "postgres")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "6"))

    summary_word_threshold: int = int(os.getenv("SUMMARY_WORD_THRESHOLD", "15"))
    summary_max_tokens: int = int(os.getenv("SUMMARY_MAX_TOKENS", "200"))


settings = Settings()
