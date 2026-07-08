# QueryWeaver

Text-to-SQL for the Kiotel PostgreSQL database, built on
[Vanna](https://github.com/vanna-ai/vanna) (RAG-based schema retrieval)
+ a hybrid pgvector/full-text vector store (its own `vectordb` Postgres
container — see below, not ChromaDB) + a hosted LLM (Llama 4 Maverick by
default, via any OpenAI-compatible endpoint) for SQL generation.

See `architecture.md` for the full design and why RAG-based retrieval beats
stuffing the whole schema into every prompt.

## Run with Docker (recommended — no local Python install needed)

`.env` is the single place you configure the database connection and LLM
credentials — copy it first:

```bash
cd queryweaver
cp .env.example .env
```

Set your LLM credentials in `.env`:
```
LLM_PROVIDER=meta
LLM_BASE_URL=https://inference.do-ai.run/v1
LLM_API_KEY=your-api-key
LLM_MODEL=llama-4-maverick
```
Any OpenAI-compatible endpoint works here — swap `LLM_BASE_URL`/`LLM_MODEL`
for a different provider/model without touching any code.

### The Kiotel (business) database — bring your own
This repo does **not** bundle the Kiotel Postgres database — `docker-compose.yml`
has no `postgres` service. Point `.env` at wherever it already runs (a cloud
DB, another server, a Postgres you run yourself, etc.):

```
PGHOST=your-db-host.example.com
PGPORT=5432
PGDATABASE=kiotel
PGUSER=your_readonly_user
PGPASSWORD=your_password
```

`db-init/` (DDL/seed `.sql` files that auto-run on container init) only
applies if you separately run a `postgres` container of your own — it is not
wired into `docker-compose.yml` here.

### The vector store — bundled, starts automatically, no setup needed
`docker-compose.yml` **does** bundle a second, separate Postgres container:
`vectordb` (image `pgvector/pgvector:pg17`). This is *not* the Kiotel
database — it's Vanna's RAG schema-retrieval store (`src/hybrid_vectorstore.py`),
holding only table DDL, documentation strings, and example SQL, never real
row data. It's fully configured via `VECTOR_DB_*` in `.env.example` (sane
defaults are already filled in — you don't need to touch these for local use).

`docker compose up -d` starts `vectordb`, `app`, and `api` together — `app`
and `api` both wait on `vectordb`'s healthcheck before starting, so there's
no separate step to bring it up. Just run:

```bash
docker compose up -d
```

**First run only:** the first time you train or ask a question, the
container downloads a small local embedding model (fastembed,
`BAAI/bge-small-en-v1.5`) used to embed schema/questions for retrieval — this
needs outbound internet access once. It's cached in the `fastembed_model_cache`
Docker volume afterwards, so this only happens once across restarts (until
you run `docker compose down -v`).

---

Then, from the host:

```bash
# One-time: train Vanna's vector store on the schema
docker compose exec app python -m src.train_vanna

# Ask a question
docker compose exec app python -m src.main "How many devices are currently licensed?"

# Check accuracy
docker compose exec app python -m tests.eval_accuracy --verbose
```

Services:
| Service    | Purpose                          | Port  |
|------------|-----------------------------------|-------|
| `vectordb` | Vanna's RAG schema-retrieval store (pgvector) — bundled, auto-starts | 5434 (host) → 5432 |
| `app`      | CLI container (train/ask/eval via `docker compose exec`) | — |
| `api`      | HTTP wrapper around the same pipeline | 8000 |

The Kiotel database itself is **not** one of these services — see above.
The LLM itself is hosted externally (`LLM_BASE_URL`) — there's no local
model-serving container to run.

To tear down: `docker compose down` (add `-v` to also wipe DB/vector-store volumes).

## Local (non-Docker) setup

You need **two** Postgres instances reachable: your Kiotel business DB
(`PGHOST`/`PGUSER`/...) and a **pgvector-enabled** Postgres for the retrieval
store (`VECTOR_DB_*`) — e.g. run just the bundled vector store via Docker
(`docker compose up -d vectordb`, exposed on host port `5434`) and point
`VECTOR_DB_HOST=localhost`, `VECTOR_DB_PORT=5434` at it, or use any other
Postgres with `CREATE EXTENSION vector` available.

```bash
cd queryweaver

# 1. Python deps
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure DB connections + LLM credentials
cp .env.example .env             # fill in Postgres (business + vector) + LLM_API_KEY details

# 3. Train once — embeds all table DDLs + examples into the vector store
#    (downloads the fastembed embedding model on first run — needs internet)
python -m src.train_vanna
```

## Usage

```bash
python -m src.main "How many devices are currently licensed?"
python -m src.main "List the 10 most recent transactions" --no-execute
```

## HTTP API

A `queryweaver-api` container runs alongside `app`, exposing the same
guarded pipeline over HTTP on port `8000`.

```bash
docker compose up -d          # starts vectordb, app, api
docker compose exec app python -m src.train_vanna   # train once (shared vector store)
```

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many devices are currently licensed?"}'
```

```json
{
  "question": "How many devices are currently licensed?",
  "sql": "SELECT COUNT(*) AS count FROM devices WHERE is_licensed = true\nLIMIT 200",
  "rows": [{"count": 42}]
}
```

GET variant for quick browser testing:
```
http://localhost:8000/ask?question=How%20many%20devices%20are%20licensed%3F
```

Interactive Swagger docs: `http://localhost:8000/docs`
Health check: `GET /health`

**Auth:** open by default (fine for local/dev). To require a shared secret,
set `API_KEY` in `.env`, then pass it as a header on every request:
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret" \
  -d '{"question": "..."}'
```
This is a shared-secret header, not real user auth/authorization — put a
proper auth layer (or keep it behind a private network) in front of this
before exposing it beyond localhost/your own infra.

Running the API without Docker:
```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

## Checking accuracy

`tests/eval_cases.json` holds labeled (question, gold SQL) pairs. Run:

```bash
python -m tests.eval_accuracy --verbose
```

For each case this generates SQL, runs both the generated and gold queries
against your DB, and compares the **result rows** (not the SQL text — two
differently-worded queries can be equally correct). It prints an overall
`execution_accuracy` score plus per-case detail so you can see exactly which
questions failed and why.

Start with 15-30 real questions your team actually asks, covering the
tables/joins you care about most, and re-run this after every training
change (new examples, new model, new prompt) to see if accuracy actually
improved rather than guessing.

## Improving accuracy
Retrieval quality (which tables get pulled in for a given question) is the
main accuracy lever — more than model size. Add real question→SQL examples
to `schema/training_examples.json`:

```json
{
  "question": "How many devices are currently licensed?",
  "sql": "SELECT COUNT(*) FROM devices WHERE is_licensed = true"
}
```

Re-run `python -m src.train_vanna` after adding examples — it trains on both
the table DDL and every example in that file. Keep these questions distinct
from `tests/eval_cases.json`, since training on the exact eval questions
would make the accuracy score meaningless (the model would just recall the
trained answer instead of generalizing).

## Project layout

```
queryweaver/
├── architecture.md
├── README.md
├── requirements.txt
├── .env.example
├── .vscode/
│   ├── settings.json
│   ├── launch.json
│   └── extensions.json
├── schema/
│   ├── schema_context.json      # table/column/FK schema, source for DDL generation
│   └── training_examples.json   # hand-written question -> SQL training pairs
├── src/
│   ├── config.py
│   ├── db.py
│   ├── schema_loader.py         # schema JSON -> DDL statements for training
│   ├── text_to_sql.py           # Vanna (hybrid pgvector store + hosted LLM) setup
│   ├── hybrid_vectorstore.py    # pgvector + full-text retrieval store (the `vectordb` service)
│   ├── train_vanna.py           # one-time vector store training
│   ├── sql_guard.py             # read-only / single-statement enforcement
│   ├── result_formatter.py      # summarizes long fields, raw-mode escape hatch
│   └── main.py
└── tests/
    └── test_sql_guard.py
```

## Tests

```bash
pytest
```
