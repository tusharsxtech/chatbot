import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from configs.settings import get_settings
from configs.logging_config import get_logger
from src.generation.rag_chain import RAGChain, ChatMessage

logger = get_logger(__name__)
_rag_chain: Optional[RAGChain] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag_chain
    logger.info("initializing_rag_chain")
    _rag_chain = RAGChain()
    # Warm up — triggers BM25 index load and model loading before first real query
    try:
        logger.info("warming_up_rag")
        _rag_chain.query("warmup")
        logger.info("rag_warmup_complete")
    except Exception as e:
        logger.warning("rag_warmup_failed", error=str(e))
    yield
    logger.info("shutting_down")


app = FastAPI(
    title="Kiotel RAG API",
    version="1.0.0",
    description="Production RAG pipeline for Kiotel dashboard documentation",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class MessageIn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    chat_history: Optional[List[MessageIn]] = None


class SourceDocument(BaseModel):
    content: str
    metadata: dict
    score: float


class QueryResponse(BaseModel):
    answer: str
    source_documents: List[SourceDocument]
    query_used: str
    blocked: bool
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    index_count: int
    model: str


@app.get("/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    from src.retrieval.vector_store import VectorStore
    try:
        vs = VectorStore()
        count = vs.count()
        db_status = "ok"
    except Exception as e:
        logger.error("health_db_error", error=str(e))
        count = -1
        db_status = "degraded"
    return HealthResponse(
        status=db_status,
        index_count=count,
        model=settings.llm_model,
    )


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    if _rag_chain is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="RAG chain not ready")

    history = None
    if req.chat_history:
        history = [ChatMessage(role=m.role, content=m.content) for m in req.chat_history]

    t0 = time.perf_counter()
    response = _rag_chain.query(req.question, chat_history=history)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    sources = [
        SourceDocument(
            content=d["content"],
            metadata=d.get("metadata", {}),
            score=d.get("rerank_score", d.get("hybrid_score", 0.0)),
        )
        for d in response.source_documents
    ]

    return QueryResponse(
        answer=response.answer,
        source_documents=sources,
        query_used=response.query_used,
        blocked=response.blocked,
        latency_ms=round(elapsed_ms, 2),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred."},
    )
