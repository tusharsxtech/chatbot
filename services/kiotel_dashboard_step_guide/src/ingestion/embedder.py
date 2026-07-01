from functools import lru_cache
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from configs.settings import get_settings
from configs.logging_config import get_logger

logger = get_logger(__name__)

_query_embed_cache: dict[str, list[float]] = {}
_QUERY_CACHE_MAX = 512


class BGEEmbedder:
    _instance: "BGEEmbedder | None" = None

    def __init__(self):
        settings = get_settings()
        logger.info("loading_embedding_model", model=settings.embedding_model)
        self.model = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
        )
        self.batch_size = settings.embedding_batch_size
        self.query_prefix = "Represent this sentence for searching relevant passages: "

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        if text in _query_embed_cache:
            return _query_embed_cache[text]
        prefixed = f"{self.query_prefix}{text}"
        embedding = self.model.encode([prefixed], normalize_embeddings=True)
        result = embedding[0].tolist()
        if len(_query_embed_cache) >= _QUERY_CACHE_MAX:
            _query_embed_cache.pop(next(iter(_query_embed_cache)))
        _query_embed_cache[text] = result
        return result

    def embed_queries(self, texts: List[str]) -> List[List[float]]:
        prefixed = [f"{self.query_prefix}{t}" for t in texts]
        embeddings = self.model.encode(
            prefixed,
            batch_size=self.batch_size,
            normalize_embeddings=True,
        )
        return embeddings.tolist()


@lru_cache(maxsize=1)
def get_embedder() -> BGEEmbedder:
    return BGEEmbedder()
