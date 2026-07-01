import concurrent.futures
from typing import List

from configs.settings import get_settings
from configs.logging_config import get_logger
from src.retrieval.vector_store import VectorStore
from src.retrieval.bm25_index import BM25Index

logger = get_logger(__name__)


class HybridRetriever:
    def __init__(self):
        settings = get_settings()
        self.alpha = settings.hybrid_alpha
        self.top_k_retrieval = settings.top_k_retrieval
        self.top_k_rerank = settings.top_k_rerank
        self.vector_store = VectorStore()
        self.bm25_index = BM25Index()

    def retrieve(self, query: str) -> List[dict]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            dense_future = executor.submit(
                self.vector_store.similarity_search, query, top_k=self.top_k_retrieval
            )
            bm25_future = executor.submit(
                self.bm25_index.search, query, top_k=self.top_k_retrieval
            )
            dense_results = dense_future.result()
            bm25_results = bm25_future.result()

        fused = self._reciprocal_rank_fusion(dense_results, bm25_results)

        reranked = fused[:self.top_k_rerank]
        logger.info(
            "retrieval_complete",
            dense=len(dense_results),
            bm25=len(bm25_results),
            fused=len(fused),
            final=len(reranked),
        )
        return reranked

    def _reciprocal_rank_fusion(
        self,
        dense: List[dict],
        bm25: List[dict],
        k: int = 60,
    ) -> List[dict]:
        scores: dict[str, float] = {}
        content_map: dict[str, dict] = {}

        for rank, hit in enumerate(dense):
            key = hit["content"][:200]
            scores[key] = scores.get(key, 0.0) + self.alpha / (k + rank + 1)
            content_map[key] = hit

        for rank, hit in enumerate(bm25):
            key = hit["content"][:200]
            scores[key] = scores.get(key, 0.0) + (1 - self.alpha) / (k + rank + 1)
            if key not in content_map:
                content_map[key] = hit

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for key, score in ranked:
            entry = dict(content_map[key])
            entry["hybrid_score"] = score
            results.append(entry)
        return results
