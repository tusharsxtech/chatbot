import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.ingestion.loader import MarkdownLoader, KiotelChunker, Document

SAMPLE_MD = """# Part 1 — Overview

This is the overview section. It explains core concepts.

## Section A

Section A details how agents sign in using an Agent ID and password.
There are multiple steps involved in the sign-in process.

## Section B

Section B describes the observer model. Only one agent can control a device at a time.
"""


@pytest.fixture
def sample_document():
    return Document(
        doc_id="test-doc-001",
        content=SAMPLE_MD,
        metadata={"source": "test.md", "filename": "test.md"},
    )


def test_chunker_produces_chunks(sample_document):
    chunker = KiotelChunker(max_words=50, min_words=5)
    chunks = chunker.chunk([sample_document])
    assert len(chunks) > 0
    for c in chunks:
        assert c.content.strip()
        assert c.doc_id == "test-doc-001"
        assert c.chunk_id


def test_chunker_splits_long_section(sample_document):
    chunker = KiotelChunker(max_words=10, min_words=2)
    chunks = chunker.chunk([sample_document])
    assert len(chunks) > 1


def test_chunk_metadata(sample_document):
    chunker = KiotelChunker(max_words=50, min_words=5)
    chunks = chunker.chunk([sample_document])
    for c in chunks:
        assert "source" in c.metadata
        assert "breadcrumb" in c.metadata


def test_loader_file(tmp_path):
    md_file = tmp_path / "docs.md"
    md_file.write_text(SAMPLE_MD)
    loader = MarkdownLoader(str(md_file))
    docs = loader.load()
    assert len(docs) == 1
    assert SAMPLE_MD in docs[0].content


def test_loader_directory(tmp_path):
    for i in range(3):
        (tmp_path / f"doc{i}.md").write_text(f"# Doc {i}\nContent {i}")
    loader = MarkdownLoader(str(tmp_path))
    docs = loader.load()
    assert len(docs) == 3
