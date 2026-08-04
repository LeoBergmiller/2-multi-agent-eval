"""SQL guardrail rejection cases (architecture.md §4, §7.7).

DuckDB has more escape hatches than Postgres, so the interesting cases are the
ones a naive "starts with SELECT" check lets through: `COPY ... TO` writes a
file, `ATTACH` opens another database, and `read_csv('/etc/passwd')` parses with
a **Select root** and reads an arbitrary file that a read-only connection is
happy to serve.
"""

from __future__ import annotations

import pytest

from analyst.mcp.guards import MAX_ROWS_HARD_CAP, SqlGuardError, validate_sql

ALLOWED = [
    pytest.param("SELECT count(*) FROM encounters", id="aggregate"),
    pytest.param("SELECT * FROM patients LIMIT 5", id="explicit-limit"),
    pytest.param(
        "WITH c AS (SELECT * FROM encounters) SELECT count(*) FROM c", id="cte"
    ),
    pytest.param(
        "SELECT e.Id FROM encounters e JOIN patients p ON e.PATIENT = p.Id", id="join"
    ),
    pytest.param("/* lead */ SELECT 1 -- trail", id="comments"),
    pytest.param("SELECT * FROM organizations ORDER BY NAME", id="order-by"),
]

REJECTED = [
    # DML
    pytest.param("INSERT INTO encounters VALUES (1)", id="insert"),
    pytest.param("UPDATE encounters SET STOP = NULL", id="update"),
    pytest.param("DELETE FROM encounters", id="delete"),
    # DDL
    pytest.param("CREATE TABLE x AS SELECT 1", id="create"),
    pytest.param("DROP TABLE encounters", id="drop"),
    pytest.param("ALTER TABLE encounters ADD COLUMN c INT", id="alter"),
    # Filesystem and attachment — the DuckDB-specific escape hatches
    pytest.param("COPY (SELECT * FROM encounters) TO '/tmp/leak.csv'", id="copy-to"),
    pytest.param("COPY encounters FROM '/tmp/x.csv'", id="copy-from"),
    pytest.param("ATTACH '/tmp/other.db' AS o", id="attach"),
    pytest.param("DETACH o", id="detach"),
    # Session and extension mutation
    pytest.param("PRAGMA database_list", id="pragma"),
    pytest.param("INSTALL httpfs", id="install"),
    pytest.param("LOAD httpfs", id="load"),
    pytest.param("SET memory_limit = '1GB'", id="set"),
    pytest.param("CALL pragma_version()", id="call"),
    # CTE-wrapped writes: the root node is the write, not the WITH
    pytest.param(
        "WITH c AS (SELECT 1) INSERT INTO encounters SELECT * FROM c", id="cte-insert"
    ),
    pytest.param("WITH c AS (SELECT 1) DELETE FROM encounters", id="cte-delete"),
    # Arbitrary file reads that parse as a plain SELECT
    pytest.param("SELECT * FROM read_csv('/etc/passwd')", id="read-csv-exfil"),
    pytest.param("SELECT * FROM read_parquet('/tmp/x.pq')", id="read-parquet"),
    pytest.param("SELECT * FROM glob('/**')", id="glob"),
    pytest.param(
        "SELECT * FROM (SELECT * FROM read_csv('/etc/passwd')) t",
        id="read-csv-in-subquery",
    ),
    # Multi-statement
    pytest.param("SELECT 1; SELECT 2", id="two-selects"),
    pytest.param("SELECT 1; DROP TABLE encounters", id="select-then-drop"),
    # Tables outside the allow-list
    pytest.param("SELECT * FROM sqlite_master", id="sqlite-master"),
    pytest.param("SELECT * FROM information_schema.tables", id="information-schema"),
    # Malformed
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace"),
    pytest.param("NOT SQL AT ALL {{", id="unparseable"),
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed_queries_pass(sql: str) -> None:
    assert validate_sql(sql)


@pytest.mark.parametrize("sql", REJECTED)
def test_rejected_queries_raise(sql: str) -> None:
    with pytest.raises(SqlGuardError):
        validate_sql(sql)


def test_limit_is_forced_when_absent() -> None:
    assert "LIMIT 1000" in validate_sql("SELECT * FROM encounters")


def test_oversized_limit_is_clamped() -> None:
    out = validate_sql("SELECT * FROM encounters LIMIT 999999", max_rows=10)
    assert "LIMIT 10" in out
    assert "999999" not in out


def test_smaller_caller_limit_is_respected() -> None:
    assert "LIMIT 5" in validate_sql("SELECT * FROM encounters LIMIT 5", max_rows=1000)


def test_max_rows_cannot_exceed_hard_cap() -> None:
    out = validate_sql("SELECT * FROM encounters", max_rows=MAX_ROWS_HARD_CAP * 100)
    assert f"LIMIT {MAX_ROWS_HARD_CAP}" in out


def test_cte_name_is_not_mistaken_for_a_disallowed_table() -> None:
    """A CTE alias is a reference to this query, not to an unknown table."""
    assert validate_sql("WITH tmp AS (SELECT 1) SELECT * FROM tmp")
