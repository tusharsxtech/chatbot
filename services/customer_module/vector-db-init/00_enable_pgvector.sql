

-- Runs automatically on first start of the standalone `vectordb` container
-- (empty volume only). POSTGRES_DB/USER/PASSWORD env vars already create
-- the vanna_vectors database and vanna role natively — this just enables
-- the pgvector extension inside that database.
CREATE EXTENSION IF NOT EXISTS vector;
