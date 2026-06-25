from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "openai"
    llm_base_url: str = "https://inference.do-ai.run/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen3-32b"

    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32

    pg_dsn: str = "postgresql://rag:rag@localhost:5432/kiotel_rag"
    bm25_index_path: str = "./data/indexes/bm25_index.pkl"

    hybrid_alpha: float = 0.6
    top_k_retrieval: int = 20
    top_k_rerank: int = 5

    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    ragas_llm_model: str = "alibaba-qwen3-32b"
    ragas_llm_base_url: str = "https://inference.do-ai.run/v1"
    ragas_llm_api_key: str = ""

    guardrail_relevance_threshold: float = 0.30
    guardrail_max_input_tokens: int = 2000
    guardrail_max_output_tokens: int = 1500
    guardrail_banned_topics: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    log_level: str = "INFO"
    data_dir: str = "./data/raw"
    chunk_size: int = 300
    chunk_min_words: int = 30

    @property
    def banned_topics_list(self) -> list[str]:
        if not self.guardrail_banned_topics:
            return []
        return [t.strip() for t in self.guardrail_banned_topics.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
