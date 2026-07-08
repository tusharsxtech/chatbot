"""QueryWeaver CLI: ask a natural-language question, get SQL + results."""
import argparse
import json
import sys

from src.config import settings
from src.text_to_sql import question_to_sql
from src.sql_guard import validate_sql, ensure_limit, UnsafeSQLError
from src.db import run_query
from src.result_formatter import format_rows


_NEEDS_DATA_LOOKUP_MARKER = "not allowed to see the data"


def ask(question: str, execute: bool = True) -> dict:
    raw_sql = question_to_sql(question)

    if _NEEDS_DATA_LOOKUP_MARKER in raw_sql:
        return {
            "question": question,
            "error": (
                "This question needs an extra lookup step (e.g. checking which "
                "values exist in a column) that's disabled for safety. Try "
                "rephrasing with the exact value you're looking for."
            ),
        }

    try:
        safe_sql = validate_sql(raw_sql)
    except UnsafeSQLError as e:
        return {"question": question, "generated_sql": raw_sql, "error": str(e)}

    safe_sql = ensure_limit(safe_sql, settings.default_row_limit)

    result = {"question": question, "sql": safe_sql}

    if execute:
        try:
            rows = run_query(safe_sql)
        except Exception as e:  # noqa: BLE001 - report a bad/hallucinated query, don't crash
            result["error"] = str(e)
            return result
        result["rows"] = format_rows(rows, question)

    return result


def main():
    parser = argparse.ArgumentParser(description="QueryWeaver: NL -> SQL -> Postgres")
    parser.add_argument("question", help="Natural language question")
    parser.add_argument("--no-execute", action="store_true", help="Only print SQL, don't run it")
    args = parser.parse_args()

    output = ask(args.question, execute=not args.no_execute)
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())
