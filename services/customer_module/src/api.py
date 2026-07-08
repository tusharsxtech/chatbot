"""QueryWeaver HTTP API.

Exposes the same guarded NL -> SQL -> Postgres pipeline used by the CLI
(src/main.py: ask()) as a REST endpoint.

Run directly:
    uvicorn src.api:app --host 0.0.0.0 --port 8000

Docs (Swagger UI) once running: http://localhost:8000/docs
"""
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from src.main import ask

app = FastAPI(
    title="QueryWeaver API",
    description="Natural language -> SQL -> Postgres, with read-only guard rails.",
    version="1.0.0",
)

# Optional shared-secret auth. Set API_KEY in the environment to require it;
# leave unset to run the API open (fine for local/dev use only).
API_KEY = os.getenv("API_KEY", "")


def _check_api_key(x_api_key: str | None) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, examples=["How many devices are currently licensed?"])
    execute: bool = Field(default=True, description="If false, only generate/validate SQL, don't run it.")


class AskResponse(BaseModel):
    question: str
    sql: str | None = None
    generated_sql: str | None = None
    rows: list[dict] | None = None
    error: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(payload: AskRequest, x_api_key: str | None = Header(default=None)):
    _check_api_key(x_api_key)
    try:
        result = ask(payload.question, execute=payload.execute)
    except Exception as e:  # noqa: BLE001 - surface as a clean 500 instead of a stack trace
        raise HTTPException(status_code=500, detail=str(e)) from e
    return result


@app.get("/ask", response_model=AskResponse)
def ask_endpoint_get(question: str, execute: bool = True, x_api_key: str | None = Header(default=None)):
    """GET variant for quick manual testing via browser/curl, e.g.:
    /ask?question=How%20many%20devices%20are%20licensed%3F
    """
    _check_api_key(x_api_key)
    try:
        result = ask(question, execute=execute)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return result
