# doc-chat-service

FastAPI service with a single endpoint, `POST /chat`: it answers a chat query
using only the property document(s) owned by a given `device_id`, stored in
Postgres, converted from HTML to Markdown, filtered down to relevant context
by a hosted LLM (Llama 4 Maverick via DigitalOcean's inference API by
default), and streamed back to the client over Server-Sent Events as a short
answer.

## Architecture

```
client --POST /chat--> FastAPI (async) --SQL--> Postgres (property_document_contents)
                              |
                              +--HTML->Markdown--+
                              |
                              +--stream--> LLM provider (/chat/completions) --tokens--> SSE --> client
```

- **Postgres**: `property_document_contents(id, property_document_id, device_id,
  content_html, word_count, updated_by_agent_id, ...)`. In production this
  table is owned by the shared kiosk-dashboard database, not this service —
  every query here runs inside a Postgres `READ ONLY` transaction, enforced
  by the database regardless of the connecting role's grants. A request is
  scoped to one `device_id`; the most recently updated matching rows are
  fetched.
- **FastAPI**: async end-to-end (asyncpg + SQLAlchemy async, httpx async
  streaming to the LLM provider, `StreamingResponse` back to the client). No
  blocking calls in the request path.
- **Markdown conversion**: `content_html` is converted to Markdown (headings,
  lists, links, emphasis preserved as syntax) before being placed in the
  prompt, so the model sees document structure instead of raw HTML tags.
- **LLM provider**: any OpenAI-compatible `/chat/completions` endpoint,
  called with `stream: true`. Given a system prompt containing the Markdown
  doc content and an instruction to extract only the relevant part and
  answer briefly, plus the user's query.

## Layout

```
doc-chat-service/
├── Dockerfile              ← the only Dockerfile — builds the FastAPI image
├── docker-compose.yml      ← orchestrates api + postgres
├── .env.example
├── api/
│   ├── requirements.txt
│   └── app/*.py            ← FastAPI source, copied into the image by Dockerfile
└── db/init.sql             ← Postgres schema + seed data (mounted into postgres, no image build needed)
```

Only the API needs a custom image, so it's the only `Dockerfile`, built with
context `.` (repo root) so it can reach `api/requirements.txt` and
`api/app`. Postgres runs the official upstream image unmodified — it gets
its schema via a mounted `init.sql` (see `docker-compose.yml`).

## Run it

```bash
cp .env.example .env   # then fill in LLM_API_KEY and Postgres settings
docker compose up --build
```

## Call it

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
        "query": "how do I reset it?",
        "user_role": "agent",
        "device_id": "device-001"
      }'
```

Response is `text/event-stream`:

```
event: start
data: {"docs":[1,2],"model":"llama-4-maverick"}

event: token
data: {"content":"To"}

event: token
data: {"content":" reset"}
...
event: done
data: {}
```

## Endpoints

- `GET /health` — liveness/readiness check used by the Docker healthcheck.
- `POST /chat` — the only functional endpoint.

### Request schema (`POST /chat`)

| field       | type   | required | notes                                     |
|-------------|--------|----------|--------------------------------------------|
| query       | string | yes      | the user's question                        |
| user_role   | string | yes      | **authorization gate, not a style hint.** Request is rejected with `403` unless this equals `REQUIRED_USER_ROLE` (default `"agent"`) |
| device_id   | string | yes      | selects which device's documents to search |

- Returns `403` if `user_role` doesn't match the configured required role —
  checked first, before any DB or LLM call.
- Returns `404` if no documents match `device_id`.

## Config (env vars, see `.env.example`)

- `LLM_PROVIDER` — free-text label for logging/docs (e.g. `meta`).
- `LLM_BASE_URL` — base URL of an OpenAI-compatible API; `/chat/completions`
  is appended. Defaults to DigitalOcean's inference endpoint.
- `LLM_API_KEY` — bearer token sent as `Authorization: Bearer <key>`.
- `LLM_MODEL` — model name passed in the request body, defaults to
  `llama-4-maverick`.
- `LLM_REQUEST_TIMEOUT` — per-request timeout in seconds (default 120).
- `MAX_DOCS_PER_QUERY`, `MAX_CHARS_PER_DOC`, `MAX_TOTAL_CONTEXT_CHARS` —
  bound how much document content gets stuffed into the prompt so the
  model's context window isn't blown.
- `CORS_ALLOW_ORIGINS` — comma-separated, or `*`.
- `REQUIRED_USER_ROLE` — defaults to `agent`. Requests where `user_role`
  doesn't match this are rejected with `403` before any DB/LLM work.

## Notes on "prod-level" — what's actually covered and what isn't

**Covered:**
- Fully async end-to-end: pooled async SQLAlchemy (`pool_pre_ping=True`),
  httpx async streaming to the LLM provider, `StreamingResponse` to the
  client — no blocking calls in the request path.
- `postgres` has a healthcheck; `api` won't start serving until it's
  actually ready.
- Container runs as a non-root user.
- Rate limiting: `RATE_LIMIT_PER_MINUTE` (default 30/min) per client IP via
  `slowapi`, in-memory. **This only works correctly with a single uvicorn
  worker/replica** (see `Dockerfile` — `--workers 1`), since the counter
  lives in process memory. If you need to scale to multiple replicas, swap
  the limiter's storage for Redis (`slowapi` supports it out of the box)
  and add a `redis` service to `docker-compose.yml`.
- Structured request logging with a per-request `X-Request-Id`, request
  method/path/status/duration on every call (`app/middleware.py`).
- Global error handling: request validation errors → `422` with details,
  DB errors → `503` (not a stack trace), any other unhandled exception →
  logged with a traceback and returned as a generic `500` (no internals
  leaked to the client). LLM/HTTP errors during streaming are caught and
  sent as a terminal `error` SSE event instead of hanging the connection.
- Request body size capped (`MAX_REQUEST_BODY_BYTES`, default 20KB) before
  it touches the DB or LLM.

**Not covered — explicitly, by your choice, for now:**
- **No authentication.** `user_role` is a self-declared field in the request
  body, not an identity check — any caller can send `"user_role": "agent"`
  and pass the gate. It filters out accidental/wrong-role callers (e.g. a
  different internal service that shouldn't be hitting this endpoint), but
  it is **not** a security boundary against a malicious client. Anyone who
  can reach the `api` container's port can still query any `device_id`.
  Fine behind a private network / internal VPC where only the trusted
  agent service can reach this port; add a real API key or JWT check in
  `app/main.py` before this is exposed anywhere less trusted.
- **CORS defaults to `*`** — tighten `CORS_ALLOW_ORIGINS` before prod.

**On latency:** there's no hard "<300ms" total-response guarantee, and for
a streaming LLM answer that isn't the right metric — the model streams
tokens as it generates them, so total time scales with answer length by
design. What's actually true here: the DB lookup + prompt build add
negligible overhead (single indexed query, no blocking I/O), so
**time-to-first-token is dominated entirely by the LLM provider's own
queueing + first-token latency**, which this service doesn't control.

- Access control beyond `device_id` scoping is not implemented —
  `user_role` only shapes whether the request is processed at all today. If
  you need per-role document authorization, add a `min_role` column to
  `property_document_contents` and filter in
  `repository.get_property_document_contents_for_device`.
