"""Run once (or after schema changes) to train Vanna's vector store.

Usage:
    python -m src.train_vanna
"""
from src.text_to_sql import train_from_schema, train_from_examples, train_from_documentation

if __name__ == "__main__":
    ddl_count = train_from_schema()
    example_count = train_from_examples()
    doc_count = train_from_documentation()
    print(
        f"Trained Vanna on {ddl_count} table DDL statements, "
        f"{example_count} question->SQL examples, "
        f"and {doc_count} documentation strings."
    )
