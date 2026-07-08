import contextvars
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("doc-chat-service.access")

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, logs one structured line per request, and
    converts any exception that escapes the endpoint into a 500 JSON
    response instead of leaking a bare traceback to the client."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        except Exception:
            logger.exception(
                "unhandled_exception method=%s path=%s",
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
                headers={"X-Request-Id": request_id},
            )
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "request method=%s path=%s status=%d duration_ms=%.1f",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )
            request_id_var.reset(token)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body exceeds {self.max_bytes} bytes"},
            )
        return await call_next(request)
