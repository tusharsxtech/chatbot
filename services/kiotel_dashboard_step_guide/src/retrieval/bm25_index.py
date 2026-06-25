import pickle
import re
from pathlib import Path
from typing import List, Optional

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from rank_bm25 import BM25Okapi

from configs.settings import get_settings
from configs.logging_config import get_logger
from src.ingestion.loader import Chunk

logger = get_logger(__name__)

try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)

try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords", quiet=True)

_STOP_WORDS = set(stopwords.words("english"))


def tokenize(text: str) -> List[str]:
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    tokens = word_tokenize(text)
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


class BM25Index:
    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.chunks: List[dict] = []
        self.index_path = Path(get_settings().bm25_index_path)

    def build(self, chunks: List[Chunk]) -> None:
        self.chunks = [
            {"content": c.content, "metadata": c.metadata, "chunk_id": c.chunk_id}
            for c in chunks
        ]
        tokenized_corpus = [tokenize(c.content) for c in chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        self._save()
        logger.info("bm25_index_built", doc_count=len(chunks))

    def search(self, query: str, top_k: int = 20) -> List[dict]:
        if self.bm25 is None:
            self._load()
        if self.bm25 is None:
            logger.warning("bm25_index_not_loaded")
            return []
        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = []
        max_score = max(scores[top_indices[0]], 1e-9)
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            results.append({
                "content": self.chunks[idx]["content"],
                "metadata": self.chunks[idx]["metadata"],
                "score": float(scores[idx] / max_score),
            })
        return results

    def _save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump({"bm25": self.bm25, "chunks": self.chunks}, f)
        logger.info("bm25_index_saved", path=str(self.index_path))

    def _load(self) -> None:
        if not self.index_path.exists():
            logger.error("bm25_index_not_found", path=str(self.index_path))
            return
        with open(self.index_path, "rb") as f:
            data = pickle.load(f)
        self.bm25 = data["bm25"]
        self.chunks = data["chunks"]
        logger.info("bm25_index_loaded", doc_count=len(self.chunks))
