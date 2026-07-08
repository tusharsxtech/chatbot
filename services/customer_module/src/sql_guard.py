"""Static validation layer: only allow single, read-only SELECT statements."""
import re

from src.schema_loader import load_schema

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|"
    r"COPY|EXECUTE|CALL|VACUUM|MERGE)\b",
    re.IGNORECASE,
)

ALLOWED_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


class UnsafeSQLError(ValueError):
    pass


def validate_sql(sql: str) -> str:
    """Raises UnsafeSQLError if the SQL is not a safe single SELECT."""
    cleaned = sql.strip().strip(";").strip()

    if not ALLOWED_START.match(cleaned):
        raise UnsafeSQLError("Only SELECT / WITH...SELECT statements are allowed.")

    if FORBIDDEN.search(cleaned):
        raise UnsafeSQLError("Query contains a forbidden write/DDL keyword.")

    if ";" in cleaned:
        raise UnsafeSQLError("Multiple statements are not allowed.")

    return cleaned


_TIMESTAMP_PRIORITY = [
    "created_at", "posted_date", "start_time", "login_time",
    "submitted_at", "upload_date", "last_active_at", "updated_at",
]
# Matches: FROM table  |  FROM table alias  |  FROM table AS alias
_TABLE_PATTERN = re.compile(r'\bFROM\s+"?(\w+)"?(?:\s+(?:AS\s+)?(\w+))?', re.IGNORECASE)
_KEYWORDS_NOT_ALIASES = {
    "WHERE", "GROUP", "ORDER", "LIMIT", "JOIN", "ON", "INNER", "LEFT",
    "RIGHT", "FULL", "CROSS", "UNION", "HAVING",
}
_AGGREGATE_PATTERN = re.compile(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(", re.IGNORECASE)
_GROUP_BY_PATTERN = re.compile(r"\bGROUP BY\b", re.IGNORECASE)


def _has_aggregation(sql: str) -> bool:
    """True if the query aggregates (COUNT/SUM/AVG/MIN/MAX, or GROUP BY).

    In either case, blindly ordering by an arbitrary timestamp column risks
    a "column must appear in the GROUP BY clause" error, since there's no
    reliable way here to verify that column is part of the grouped/
    aggregated set — so ensure_limit skips adding ORDER BY entirely rather
    than guess.
    """
    return bool(_AGGREGATE_PATTERN.search(sql)) or bool(_GROUP_BY_PATTERN.search(sql))


def _find_order_column(table: str) -> str | None:
    """Picks the best timestamp-like column on `table` to sort "most recent first"."""
    cols = load_schema()["tables"].get(table, [])
    for candidate in _TIMESTAMP_PRIORITY:
        if candidate in cols:
            return candidate
    for col in cols:
        if col.endswith(("_at", "_date", "_time")):
            return col
    return None


def _extract_table_and_ref(sql: str) -> tuple[str, str] | None:
    """Returns (real_table_name, name_to_reference_in_this_query) — the
    reference is the alias if the query aliased the table, otherwise the
    table name itself.
    """
    match = _TABLE_PATTERN.search(sql)
    if not match:
        return None
    table, alias = match.group(1), match.group(2)
    if alias and alias.upper() in _KEYWORDS_NOT_ALIASES:
        alias = None
    return table, (alias or table)


def ensure_limit(sql: str, default_limit: int) -> str:
    """If the question didn't imply a row count, order by the most recent
    row (when the table has a timestamp-like column) and cap at
    `default_limit`. If the model already produced its own LIMIT, that's
    treated as an implied limit and left untouched.
    """
    if re.search(r"\bLIMIT\s+\d+\b", sql, re.IGNORECASE):
        return sql

    if not re.search(r"\bORDER BY\b", sql, re.IGNORECASE) and not _has_aggregation(sql):
        found = _extract_table_and_ref(sql)
        if found:
            table, ref = found
            order_col = _find_order_column(table)
            if order_col:
                sql = f'{sql}\nORDER BY "{ref}"."{order_col}" DESC'

    return f"{sql}\nLIMIT {default_limit}"
