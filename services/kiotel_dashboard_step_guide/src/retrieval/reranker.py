from functools import lru_cache
from typing import List

from sentence_transformers import CrossEncoder

from configs.settings import get_settings
from configs.logging_config import get_logger

logger = get_logger(__name__)


class Reranker:
    def __init__(self):
        settings = get_settings()
        logger.info("loading_reranker", model=settings.reranker_model)
        self.model = CrossEncoder(settings.reranker_model)

    def rerank(self, query: str, candidates: List[dict], top_k: int) -> List[dict]:
        if not candidates:
            return []
        pairs = [(query, c["content"]) for c in candidates]
        scores = self.model.predict(pairs)
        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)
        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        logger.info("reranked", input_count=len(candidates), output_count=top_k)
        return ranked[:top_k]


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    return Reranker()
