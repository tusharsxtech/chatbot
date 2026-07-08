"""Loads the condensed schema context and renders it for prompting."""
import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "schema_context.json"


def load_schema() -> dict:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def render_schema_for_prompt() -> str:
    """Render tables + columns + FKs as compact text for the LLM prompt."""
    schema = load_schema()
    lines = [f"Database: {schema['database']} ({schema['dialect']})", "", "Tables:"]

    for table, cols in schema["tables"].items():
        lines.append(f"  {table}({', '.join(cols)})")

    lines.append("")
    lines.append("Foreign keys:")
    for src, dst in schema["foreign_keys"]:
        lines.append(f"  {src} -> {dst}")

    return "\n".join(lines)


def render_ddl_statements() -> list[str]:
    """Render one approximate CREATE TABLE statement per table for Vanna training.

    Column types are generalized (TEXT) since Vanna's vector store only needs
    table/column names and relationships to retrieve relevant schema chunks —
    exact types don't affect retrieval quality. Swap in the real DDL (e.g.
    pg_dump --schema-only) for production use if you want typed training data.
    """
    schema = load_schema()
    fk_map: dict[str, list[tuple[str, str, str]]] = {}
    for src, dst in schema["foreign_keys"]:
        src_table, src_col = src.split(".")
        dst_table, dst_col = dst.split(".")
        fk_map.setdefault(src_table, []).append((src_col, dst_table, dst_col))

    statements = []
    for table, cols in schema["tables"].items():
        col_lines = [f'    "{c}" TEXT' for c in cols]
        for src_col, dst_table, dst_col in fk_map.get(table, []):
            col_lines.append(
                f'    FOREIGN KEY ("{src_col}") REFERENCES "{dst_table}"("{dst_col}")'
            )
        ddl = f'CREATE TABLE "{table}" (\n' + ",\n".join(col_lines) + "\n);"
        statements.append(ddl)

    return statements


if __name__ == "__main__":
    print(render_schema_for_prompt())
