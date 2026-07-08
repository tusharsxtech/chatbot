import pytest
from src.sql_guard import validate_sql, ensure_limit, UnsafeSQLError


def test_allows_select():
    assert validate_sql("SELECT * FROM devices") == "SELECT * FROM devices"


def test_allows_with_cte():
    sql = "WITH x AS (SELECT 1) SELECT * FROM x"
    assert validate_sql(sql) == sql


def test_blocks_insert():
    with pytest.raises(UnsafeSQLError):
        validate_sql("INSERT INTO devices (device_id) VALUES ('x')")


def test_blocks_drop():
    with pytest.raises(UnsafeSQLError):
        validate_sql("DROP TABLE devices")


def test_blocks_multi_statement():
    with pytest.raises(UnsafeSQLError):
        validate_sql("SELECT 1; SELECT 2")


def test_ensure_limit_appends_when_missing():
    out = ensure_limit("SELECT * FROM devices", 200)
    assert "LIMIT 200" in out


def test_ensure_limit_respects_existing():
    out = ensure_limit("SELECT * FROM devices LIMIT 10", 200)
    assert out.count("LIMIT") == 1
