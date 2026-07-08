"""Vanna RAG setup: hybrid (lexical + semantic) vector store for schema
retrieval + a hosted LLM reachable over an OpenAI-compatible API
(LLM_BASE_URL).

Retrieval flow at query time (this is the "pruning" step):
  1. The question is matched against previously-trained DDL / documentation
     / example SQL chunks using both Postgres full-text search and pgvector
     cosine similarity, fused via reciprocal rank fusion
     (src/hybrid_vectorstore.py).
  2. Only the top-k relevant chunks (typically the 3-6 tables that matter
     for this question) are pulled back — not the full schema.
  3. Those chunks + the question are sent to the configured LLM to
     generate SQL.

This keeps the prompt small and improves accuracy by removing irrelevant
tables that could distract the model.
"""
import json
from pathlib import Path

from openai import OpenAI
from vanna.legacy.openai import OpenAI_Chat

from src.config import settings
from src.hybrid_vectorstore import HybridPGVectorStore
from src.schema_loader import render_ddl_statements

TRAINING_EXAMPLES_PATH = Path(__file__).resolve().parent.parent / "schema" / "training_examples.json"
DOCUMENTATION_PATH = Path(__file__).resolve().parent.parent / "schema" / "documentation.json"


class MyVanna(HybridPGVectorStore, OpenAI_Chat):
    def __init__(self, client, config=None):
        HybridPGVectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, client=client, config=config)


_vn: MyVanna | None = None


def get_vanna() -> MyVanna:
    global _vn
    if _vn is not None:
        return _vn

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    _vn = MyVanna(
        client=client,
        config={
            "n_results": settings.retrieval_top_k,
            "model": settings.llm_model,
        },
    )
    _vn.connect_to_postgres(
        host=settings.pg_host,
        dbname=settings.pg_db,
        user=settings.pg_user,
        password=settings.pg_password,
        port=settings.pg_port,
    )
    return _vn


def train_from_schema() -> int:
    """One-time (or whenever schema changes) training step.

    Feeds each table's DDL into the vector store separately so retrieval
    can pull back only the tables relevant to a given question, instead of
    the whole schema.
    """
    vn = get_vanna()
    ddl_statements = render_ddl_statements()
    for ddl in ddl_statements:
        vn.train(ddl=ddl)
    return len(ddl_statements)


def train_from_examples() -> int:
    """Trains Vanna on hand-written question -> SQL examples
    (schema/training_examples.json).

    This is the single biggest accuracy lever for RAG-based text-to-SQL:
    it teaches correct join patterns for questions that span multiple
    tables, and improves retrieval since the question's embedding is
    matched against real past questions, not just table DDL.
    """
    vn = get_vanna()
    if not TRAINING_EXAMPLES_PATH.exists():
        return 0
    with open(TRAINING_EXAMPLES_PATH, "r", encoding="utf-8") as f:
        examples = json.load(f)
    for example in examples:
        vn.train(question=example["question"], sql=example["sql"])
    return len(examples)


def train_from_documentation() -> int:
    """Trains Vanna on free-text documentation strings (schema/documentation.json).

    Bridges vocabulary gaps that DDL/examples alone can't — e.g. mapping a
    business term like "property workflow" to the real tables it refers to,
    or noting where two tables lack a formal foreign key.
    """
    vn = get_vanna()
    if not DOCUMENTATION_PATH.exists():
        return 0
    with open(DOCUMENTATION_PATH, "r", encoding="utf-8") as f:
        docs = json.load(f)
    for doc in docs:
        vn.train(documentation=doc)
    return len(docs)


def question_to_sql(question: str) -> str:
    vn = get_vanna()
    sql = vn.generate_sql(question=question, allow_llm_to_see_data=False)
    return sql.strip()
