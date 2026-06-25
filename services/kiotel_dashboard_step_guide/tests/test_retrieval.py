import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch
from src.retrieval.hybrid_retriever import HybridRetriever


def _make_hits(texts, scores):
    return [
        {"content": t, "metadata": {}, "score": s}
        for t, s in zip(texts, scores)
    ]


@patch("src.retrieval.hybrid_retriever.get_reranker")
@patch("src.retrieval.hybrid_retriever.BM25Index")
@patch("src.retrieval.hybrid_retriever.VectorStore")
def test_rrf_combines_results(MockVS, MockBM25, MockReranker):
    dense = _make_hits(["doc_a", "doc_b", "doc_c"], [0.9, 0.8, 0.7])
    bm25 = _make_hits(["doc_c", "doc_d", "doc_a"], [1.0, 0.9, 0.8])

    mock_vs_instance = MagicMock()
    mock_vs_instance.similarity_search.return_value = dense
    MockVS.return_value = mock_vs_instance

    mock_bm25_instance = MagicMock()
    mock_bm25_instance.search.return_value = bm25
    MockBM25.return_value = mock_bm25_instance

    mock_reranker = MagicMock()
    mock_reranker.rerank.side_effect = lambda q, docs, top_k: docs[:top_k]
    MockReranker.return_value = mock_reranker

    retriever = HybridRetriever()
    fused = retriever._reciprocal_rank_fusion(dense, bm25)

    contents = [d["content"] for d in fused]
    assert "doc_a" in contents
    assert "doc_c" in contents
    assert "doc_a" in contents[:2] or "doc_c" in contents[:2]


@patch("src.retrieval.hybrid_retriever.get_reranker")
@patch("src.retrieval.hybrid_retriever.BM25Index")
@patch("src.retrieval.hybrid_retriever.VectorStore")
def test_retrieve_calls_reranker(MockVS, MockBM25, MockReranker):
    mock_vs_instance = MagicMock()
    mock_vs_instance.similarity_search.return_value = _make_hits(["x"], [0.9])
    MockVS.return_value = mock_vs_instance

    mock_bm25_instance = MagicMock()
    mock_bm25_instance.search.return_value = _make_hits(["x"], [1.0])
    MockBM25.return_value = mock_bm25_instance

    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = _make_hits(["x"], [0.95])
    MockReranker.return_value = mock_reranker

    retriever = HybridRetriever()
    results = retriever.retrieve("test query")

    mock_reranker.rerank.assert_called_once()
    assert len(results) == 1
