"""`run_sql` — the one MCP tool at Gate 0 (architecture.md §4).

Guardrails, in order: sqlglot AST validation (`guards.py`), a read-only DuckDB
connection, a forced LIMIT, and a wall-clock cap.

The return value is the load-bearing part. Per §4 and D21 this returns a
`ResultRef` plus schema, row count, and `head(5)` — **never** the full frame.
The frame is written to `runs/{run_id}/results/` and stays there.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import duckdb

from analyst.artifacts import ResultStore
from analyst.contracts import Contract, ResultRef
from analyst.mcp.guards import SqlGuardError, validate_sql

#: Wall-clock cap for a single query. DuckDB has no statement_timeout setting,
#: so this is enforced by interrupting the connection from a timer thread.
DEFAULT_TIMEOUT_S = 30.0


class QueryResult(Contract):
    """What `run_sql` returns to the model.

    `ok=False` is a *reported* failure, not an exception: a rejected query
    should let the model correct itself, and a guard rejection that killed the
    run would make the guardrail more damaging than the query it blocked.
    """

    ok: bool
    ref: ResultRef | None = None
    executed_sql: str | None = None
    error: str | None = None
    elapsed_ms: float = 0.0


class SqlRunner:
    """Executes validated SQL against a read-only warehouse."""

    def __init__(
        self,
        warehouse: Path,
        store: ResultStore,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        if not warehouse.is_file():
            raise FileNotFoundError(
                f"Warehouse not found at {warehouse}. Run `make data` first."
            )
        # read_only is defence in depth, not the primary control: it stops
        # writes, but not a read of an arbitrary file via read_csv(). That is
        # what the table allow-list in guards.py is for.
        self._con = duckdb.connect(str(warehouse), read_only=True)
        self._store = store
        self._timeout_s = timeout_s
        self._counter = 0

    def close(self) -> None:
        self._con.close()

    def run(self, query: str, max_rows: int = 1000) -> QueryResult:
        started = time.perf_counter()
        try:
            safe_sql = validate_sql(query, max_rows=max_rows)
        except SqlGuardError as e:
            return QueryResult(
                ok=False,
                error=str(e),
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )

        self._counter += 1
        ref_id = f"q{self._counter:03d}"

        timer = threading.Timer(self._timeout_s, self._con.interrupt)
        timer.start()
        try:
            ref = self._store.write_query(self._con, safe_sql, ref_id=ref_id)
        except duckdb.Error as e:
            return QueryResult(
                ok=False,
                executed_sql=safe_sql,
                error=f"Query failed: {e}",
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        finally:
            timer.cancel()

        return QueryResult(
            ok=True,
            ref=ref,
            executed_sql=safe_sql,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
