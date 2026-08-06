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
FIXTURES = REPO_ROOT / "data" / "fixtures"


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
    """A real DuckDB built from the committed fixtures.

    Built per-test in tmp rather than reusing data/warehouse.duckdb so the suite
    never depends on `make data` having been run.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from data.load_fixtures import build

    path = tmp_path / "warehouse.duckdb"
    build(warehouse=path, fixtures=FIXTURES)
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
