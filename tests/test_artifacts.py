"""ResultRef store and run-directory layout (architecture.md §4, §8, §7.7)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from analyst.artifacts import HEAD_ROWS, ResultStore, RunDirectory, new_run_meta
from analyst.contracts import Evidence, FinalAnswer


@pytest.fixture
def seeded(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    con.execute(
        "CREATE TABLE t AS SELECT * FROM (VALUES "
        "(1,'a'),(2,'b'),(3,NULL),(4,'d'),(5,'e'),(6,'f'),(7,'g')) AS v(n, s)"
    )
    return con


class TestResultStore:
    def test_writes_parquet_and_returns_a_reference(
        self, seeded: duckdb.DuckDBPyConnection, store: ResultStore
    ) -> None:
        ref = store.write_query(seeded, "SELECT * FROM t ORDER BY n", ref_id="q001")
        assert ref.ref_id == "q001"
        assert ref.row_count == 7
        assert ref.bytes_written > 0
        assert store.path_for("q001").is_file()

    def test_head_never_exceeds_five_rows(
        self, seeded: duckdb.DuckDBPyConnection, store: ResultStore
    ) -> None:
        """The whole point of ResultRef: the model sees a sample, never the
        frame (§4, D21)."""
        ref = store.write_query(seeded, "SELECT * FROM t ORDER BY n", ref_id="q001")
        assert ref.row_count == 7
        assert len(ref.head) == HEAD_ROWS

    def test_schema_is_captured(
        self, seeded: duckdb.DuckDBPyConnection, store: ResultStore
    ) -> None:
        ref = store.write_query(seeded, "SELECT * FROM t", ref_id="q001")
        assert [c.name for c in ref.schema_] == ["n", "s"]
        assert ref.schema_[0].dtype == "INTEGER"

    def test_nulls_survive_as_none(
        self, seeded: duckdb.DuckDBPyConnection, store: ResultStore
    ) -> None:
        """A still-admitted patient is a NULL, not the string 'None'."""
        ref = store.write_query(seeded, "SELECT * FROM t WHERE n = 3", ref_id="q001")
        assert ref.head[0]["s"] is None

    def test_empty_result_is_valid(
        self, seeded: duckdb.DuckDBPyConnection, store: ResultStore
    ) -> None:
        ref = store.write_query(seeded, "SELECT * FROM t WHERE n = 999", ref_id="q001")
        assert ref.row_count == 0
        assert ref.head == ()


class TestRunDirectory:
    def test_layout_matches_the_spec(self, runs_root: Path) -> None:
        """§8 names these paths; the README, demo app and CI gate all read
        them, so the layout is a contract."""
        run = RunDirectory("r1")
        assert run.path == runs_root / "r1"
        assert run.spans_path.name == "spans.jsonl"
        assert run.meta_path.name == "meta.json"
        assert run.plan_path.name == "plan.json"
        assert run.final_path.name == "final.json"
        assert run.eval_path.name == "eval.json"
        assert (run.path / "results").is_dir()

    def test_meta_round_trips(self, runs_root: Path) -> None:
        run = RunDirectory("r1")
        meta = new_run_meta(
            run_id="r1",
            task_id="t1",
            cassette_mode="replay",
            models={"planner": "claude-opus-5"},
            price_table_hash="abc123",
            price_table_checked="2026-08-03",
        )
        run.write_meta(meta)
        assert run.read_meta().price_table_hash == "abc123"

    def test_final_round_trips(self, runs_root: Path) -> None:
        run = RunDirectory("r1")
        final = FinalAnswer(
            answer="37",
            evidence=(Evidence(claim="37", result_ref="q001"),),
            confidence=0.95,
            numeric_value=37.0,
        )
        run.write_final(final)
        assert run.read_final().numeric_value == 37.0

    def test_json_is_written_deterministically(self, runs_root: Path) -> None:
        """Committed demo runs must not churn in git on a re-run."""
        run = RunDirectory("r1")
        payload = {"b": 2, "a": 1}
        run.write_eval(payload)
        first = run.eval_path.read_text()
        run.write_eval({"a": 1, "b": 2})
        assert run.eval_path.read_text() == first
