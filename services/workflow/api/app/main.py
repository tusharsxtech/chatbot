import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import orjson
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.llm_client import build_messages, stream_llm_chat
from app.middleware import BodySizeLimitMiddleware, RequestContextMiddleware, RequestIdFilter
from app.repository import get_property_document_contents_for_device
from app.schemas import ChatRequest

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s level=%(levelname)s logger=%(name)s request_id=%(request_id)s %(message)s",
)
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIdFilter())
logger = logging.getLogger("doc-chat-service")

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation_error path=%s errors=%s", request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("database_error path=%s", request.url.path)
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})


def sse_event(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {orjson.dumps(data).decode()}\n\n".encode()


@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.llm_model}


@app.post("/chat")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: AsyncSession = Depends(get_session),
):
    if chat_request.user_role != settings.required_user_role:
        logger.warning(
            "role_denied device_id=%s user_role=%s", chat_request.device_id, chat_request.user_role
        )
        raise HTTPException(
            status_code=403,
            detail=f"user_role must be {settings.required_user_role!r}",
        )

    contents = await get_property_document_contents_for_device(
        session=session,
        device_id=chat_request.device_id,
        limit=settings.max_docs_per_query,
    )

    if not contents:
        raise HTTPException(
            status_code=404,
            detail=f"No property documents found for device_id={chat_request.device_id!r}",
        )

    messages = build_messages(
        query=chat_request.query,
        contents=contents,
        settings=settings,
    )

    content_ids = [c.id for c in contents]

    async def event_stream() -> AsyncGenerator[bytes, None]:
        yield sse_event("start", {"docs": content_ids, "model": settings.llm_model})
        try:
            async for token in stream_llm_chat(app.state.http_client, settings, messages):
                yield sse_event("token", {"content": token})
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.exception("llm_streaming_failed device_id=%s", chat_request.device_id)
            yield sse_event("error", {"detail": str(exc)})
            return
        yield sse_event("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
