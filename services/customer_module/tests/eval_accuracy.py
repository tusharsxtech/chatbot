"""Execution-accuracy evaluation harness.

Runs each (question, gold_sql) pair from tests/eval_cases.json through the
pipeline, compares the generated SQL's result set against the gold query's
result set (order-insensitive row comparison), and reports accuracy.

This measures whether the generated SQL returns the SAME DATA as a
known-correct query -- not whether the SQL text matches, since two
differently-worded queries can be equally correct.

Usage:
    python -m tests.eval_accuracy
    python -m tests.eval_accuracy --verbose   # show every mismatch's SQL + rows
"""
import argparse
import json
from pathlib import Path

from src.text_to_sql import question_to_sql
from src.sql_guard import validate_sql, ensure_limit, UnsafeSQLError
from src.db import run_query
from src.config import settings

CASES_PATH = Path(__file__).resolve().parent / "eval_cases.json"


def _rows_to_comparable(rows: list[dict]) -> set:
    """Turn a list of row-dicts into an order-insensitive, hashable set."""
    return {tuple(sorted((k, str(v)) for k, v in row.items())) for row in rows}


def run_eval(verbose: bool = False) -> dict:
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    results = []
    passed = 0

    for case in cases:
        question = case["question"]
        gold_sql = case["gold_sql"]

        entry = {"question": question, "gold_sql": gold_sql}

        try:
            raw_sql = question_to_sql(question)
            safe_sql = validate_sql(raw_sql)
            safe_sql = ensure_limit(safe_sql, settings.default_row_limit)
            entry["generated_sql"] = safe_sql

            gold_rows = run_query(gold_sql)
            gen_rows = run_query(safe_sql)

            match = _rows_to_comparable(gold_rows) == _rows_to_comparable(gen_rows)
            entry["match"] = match
            entry["gold_row_count"] = len(gold_rows)
            entry["generated_row_count"] = len(gen_rows)

            if match:
                passed += 1

        except (UnsafeSQLError, Exception) as e:  # noqa: BLE001 - report, don't crash the run
            entry["match"] = False
            entry["error"] = str(e)

        results.append(entry)

    total = len(cases)
    accuracy = passed / total if total else 0.0

    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "execution_accuracy": round(accuracy, 3),
    }

    print(json.dumps(summary, indent=2))

    if verbose:
        print("\nDetail:")
        for r in results:
            print(json.dumps(r, indent=2, default=str))

    return {"summary": summary, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate text-to-SQL execution accuracy")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    run_eval(verbose=args.verbose)
