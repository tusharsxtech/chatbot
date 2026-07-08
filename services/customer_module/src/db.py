"""PostgreSQL connection + safe execution."""
import psycopg2
import psycopg2.extras

from src.config import settings


def get_connection():
    conn = psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        dbname=settings.pg_db,
        user=settings.pg_user,
        password=settings.pg_password,
    )
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = {settings.statement_timeout_ms}")
        cur.execute("SET default_transaction_read_only = on")
    return conn


def run_query(sql: str) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()
