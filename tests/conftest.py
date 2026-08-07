"""Shared fixtures.

Testing strategy (architecture.md §7.7): test the deterministic core hard, and
do not test prompt content, snapshot LLM output, or require an API key. Every
test here runs offline.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest

from analyst.artifacts import ResultStore

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def committed_corpus() -> Path:
    """The real metrics-dictionary corpus (architecture.md §1.5, committed)."""
    return REPO_ROOT / "data" / "metrics_dictionary"


@pytest.fixture
def runs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect `runs/` into tmp so tests never write real run directories."""
    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setattr("analyst.artifacts.store.runs_root", lambda: root)
    return root


@pytest.fixture
def cassettes_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp cassette root, also redirected globally.

    The monkeypatch matters for any test that goes through `run_task`, which
    constructs its own `CassetteStore` with no explicit root — without it a
    RECORD test would write into the committed `cassettes/`.
    """
    root = tmp_path / "cassettes"
    (root / "llm").mkdir(parents=True)
    (root / "mcp").mkdir(parents=True)
    monkeypatch.setattr("analyst.replay.store.cassettes_root", lambda: root)
    return root


@pytest.fixture
def warehouse(tmp_path: Path) -> Path:
    """A small real DuckDB, built in-process for the test that needs one.

    Synthesised here rather than loaded from committed CSVs. The Synthea warehouse is
    gitignored and takes a JDK plus minutes to build, so a suite that depended on it
    would stop running on a clean clone and in CI — and the RECORD-path test needs *a*
    database, not *the* warehouse.

    Column types mirror `data/synthea_spec.py` exactly, including `STOP TIMESTAMP`
    holding real NULLs for still-admitted patients. That is the property the SQL
    guards and the record path are actually exercised against; getting it from a
    committed CSV was incidental.

    The 37 inpatient-2023 rows make this fixture's arithmetic explicit. It is a
    property of the TEST, not an eval ground truth — `evals/tasks/` owns those, they
    are human-verified (D17), and the Gate 0 number died with the CSV fixtures.
    """
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE patients ("
            "  Id VARCHAR, BIRTHDATE DATE, DEATHDATE DATE, GENDER VARCHAR,"
            "  CITY VARCHAR, STATE VARCHAR"
            ")"
        )
        con.execute(
            "CREATE TABLE organizations ("
            "  Id VARCHAR, NAME VARCHAR, CITY VARCHAR, STATE VARCHAR"
            ")"
        )
        con.execute(
            "CREATE TABLE encounters ("
            "  Id VARCHAR, START TIMESTAMP, STOP TIMESTAMP, PATIENT VARCHAR,"
            "  ORGANIZATION VARCHAR, ENCOUNTERCLASS VARCHAR, DESCRIPTION VARCHAR,"
            "  TOTAL_CLAIM_COST DOUBLE"
            ")"
        )
        con.execute(
            "INSERT INTO patients "
            "SELECT 'p' || i, DATE '1970-01-01', NULL, 'F', 'Boston', 'MA' "
            "FROM range(50) t(i)"
        )
        con.execute(
            "INSERT INTO organizations VALUES "
            "('o1', 'Mass General', 'Boston', 'MA'), ('o2', 'Brigham', 'Boston', 'MA')"
        )
        # 37 inpatient encounters starting in 2023 — six of them still admitted, so a
        # query that assumes every stay has ended returns 31 rather than erroring.
        con.execute(
            "INSERT INTO encounters "
            "SELECT 'e2023i' || i, TIMESTAMP '2023-03-01 08:00:00' + INTERVAL (i) DAY,"
            "  CASE WHEN i < 6 THEN NULL"
            "       ELSE TIMESTAMP '2023-03-04 10:00:00' + INTERVAL (i) DAY END,"
            "  'p' || (i % 50), 'o1', 'inpatient', 'Inpatient stay', 9000.0 "
            "FROM range(37) t(i)"
        )
        # Distractors: the same class in a different year, and wellness visits in the
        # same year — the two ways to get this count wrong.
        con.execute(
            "INSERT INTO encounters "
            "SELECT 'e2022i' || i, TIMESTAMP '2022-05-01 08:00:00' + INTERVAL (i) DAY,"
            "  TIMESTAMP '2022-05-03 10:00:00' + INTERVAL (i) DAY,"
            "  'p' || (i % 50), 'o1', 'inpatient', 'Inpatient stay', 8000.0 "
            "FROM range(18) t(i)"
        )
        con.execute(
            "INSERT INTO encounters "
            "SELECT 'e2023w' || i, TIMESTAMP '2023-06-01 09:00:00' + INTERVAL (i) DAY,"
            "  TIMESTAMP '2023-06-01 09:30:00' + INTERVAL (i) DAY,"
            "  'p' || (i % 50), 'o2', 'wellness', 'Well visit', 150.0 "
            "FROM range(44) t(i)"
        )
    finally:
        con.close()
    return path


@pytest.fixture
def store(tmp_path: Path) -> ResultStore:
    return ResultStore(tmp_path / "results")


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect()
    try:
        yield connection
    finally:
        connection.close()


def write_spans(path: Path, records: list[dict[str, Any]]) -> Path:
    """Write a hand-built `spans.jsonl`, so trajectory tests need no agent."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def span(
    name: str,
    *,
    span_id: str = "aaaa000000000001",
    parent: str | None = None,
    start_ns: int = 0,
    **attributes: Any,
) -> dict[str, Any]:
    """Build one span record for a hand-made trajectory."""
    return {
        "name": name,
        "span_id": span_id,
        "trace_id": "t" * 32,
        "parent_span_id": parent,
        "start_time_ns": start_ns,
        "end_time_ns": start_ns + 1_000_000,
        "duration_ms": 1.0,
        "status": "UNSET",
        "attributes": attributes,
        "events": [],
    }
