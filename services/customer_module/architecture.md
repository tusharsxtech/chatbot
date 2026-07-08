# QueryWeaver — Text-to-SQL Architecture (Kiotel DB / PostgreSQL 17)

## Goal
Convert a natural-language question into a safe, executable read-only SQL
query against the Kiotel PostgreSQL database, run it, and return results —
using a **RAG-based** pipeline (Vanna + ChromaDB) with a hosted LLM
(Llama 4 Maverick by default, via any OpenAI-compatible endpoint) for SQL
generation.

## Why RAG-based schema retrieval instead of full-schema prompting
Feeding every table into every prompt wastes tokens and hurts accuracy —
irrelevant tables act as noise and increase the chance of a hallucinated
join. Vanna solves this with retrieval: each table's DDL is embedded and
stored once in ChromaDB (local, in-process — no external service). At
query time, only the tables semantically relevant to the question are
retrieved and passed to the model — a form of dynamic schema pruning.

## High-level flow

```
[one-time] Training step
  src/train_vanna.py
      │  embeds each table's DDL (src/schema_loader.py -> render_ddl_statements)
      │  + hand-written question->SQL examples (schema/training_examples.json)
      │  into ChromaDB (./.vanna_chroma)
      ▼
  Vector store populated (one DDL chunk per table + example Q&A pairs)

[per question]
User NL question
      │
      ▼
[1] Vanna retrieval        (src/text_to_sql.py -> get_vanna().generate_sql)
      │  embeds the question, retrieves top-k relevant table DDL chunks
      │  from ChromaDB (schema pruning — usually 3-6 tables, not all of them)
      ▼
[2] Hosted LLM (NL → SQL)  (OpenAI-compatible API, e.g. Llama 4 Maverick)
      │  generates SQL grounded only in the retrieved tables
      ▼
[3] SQL Guard              (src/sql_guard.py)
      │  validates: SELECT-only, no DDL/DML, single statement,
      │  most-recent-first ordering + LIMIT enforcement when none implied
      ▼
[4] DB Executor            (src/db.py -> psycopg2, read-only role)
      │  executes against PostgreSQL
      ▼
[5] Result Formatter       (src/result_formatter.py)
      │  summarizes long text fields (unless the question says "raw")
      ▼
Answer to user
```

## Components

| Module                     | Responsibility                                             |
|-----------------------------|-------------------------------------------------------------|
| `src/config.py`             | Loads env vars (DB creds, LLM provider/model/key, Chroma path) |
| `src/db.py`                 | Postgres connection pool, safe query execution              |
| `src/schema_loader.py`      | Loads schema JSON, renders prompt text + per-table DDL       |
| `src/text_to_sql.py`        | Vanna instance (ChromaDB + hosted LLM), retrieval + generation |
| `src/train_vanna.py`        | One-time script to embed table DDLs + examples into the vector store |
| `src/sql_guard.py`          | Static validation: blocks non-SELECT / multi-statement SQL, default ordering/limit |
| `src/result_formatter.py`   | Summarizes long fields in results, "raw" escape hatch        |
| `src/main.py`               | CLI entrypoint: question → SQL → results                     |
| `tests/`                    | Unit tests for guard rails + execution-accuracy eval harness  |

## Safety rules enforced by SQL Guard (unchanged regardless of model)
1. Only a single `SELECT` (or `WITH ... SELECT`) statement is allowed.
2. Statements containing `INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|CREATE`
   are rejected before execution.
3. Query is executed against a **read-only** DB role
   (`queryweaver_readonly`) — defense in depth, not just app-layer.
4. If the question doesn't imply a row count, the query is ordered by the
   most recent row (when a timestamp-like column exists) and capped at
   `DEFAULT_ROW_LIMIT` (default 5). If the model's own SQL already has a
   `LIMIT`, that's left untouched.
5. Query timeout enforced at the connection level (`statement_timeout`).

## LLM: hosted, OpenAI-compatible
The LLM is **not** run locally — `src/text_to_sql.py` and
`src/result_formatter.py` both talk to an OpenAI-compatible chat endpoint
configured entirely through env vars:
```
LLM_PROVIDER=meta
LLM_BASE_URL=https://inference.do-ai.run/v1
LLM_API_KEY=your-api-key
LLM_MODEL=llama-4-maverick
```
Swapping providers/models is a config change only — any endpoint that
speaks the OpenAI chat-completions API works (`vanna.legacy.openai.OpenAI_Chat`
is given a pre-configured `openai.OpenAI(api_key=..., base_url=...)` client).
Only table/column names and question text are sent to the LLM — actual row
data never is (`allow_llm_to_see_data=False` in `question_to_sql`).

## Running it locally
```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Configure .env: Postgres creds + LLM_API_KEY (see .env.example)

# 3. Train once (embeds all table DDLs + examples into ChromaDB)
python -m src.train_vanna

# 4. Ask questions
python -m src.main "How many devices are currently licensed?"
```

## Recommended Postgres role
```sql
CREATE ROLE queryweaver_readonly LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE kiotel TO queryweaver_readonly;
GRANT USAGE ON SCHEMA public TO queryweaver_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO queryweaver_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO queryweaver_readonly;
```

## Extension points
- Add example question→SQL pairs to `schema/training_examples.json` — this
  is the single biggest accuracy lever for RAG-based text-to-SQL, more so
  than model size.
- Swap `LLM_MODEL`/`LLM_BASE_URL` for a different hosted model without
  touching any other code.
- Add a FastAPI wrapper (`src/api.py`) to expose `/ask` as an HTTP endpoint.
