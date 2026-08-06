"""`search_metric_definitions`, its span attributes, and its cassette key.

Every test here runs without the `[rag]` extra and without an index — a fake backend
stands in. That is the point: the tool, its telemetry and its cassette keying are all
part of the hermetic path, and only the retrieval itself is optional.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from analyst.contracts import RetrievalResult, RetrievedChunk
from analyst.mcp.client import ToolCallResult
from analyst.mcp.tools.retrieval import MAX_K, DefinitionSearcher
from analyst.replay import CassetteStore, ReplayingMCPClient
from analyst.replay.store import CassetteMode
from analyst.telemetry.attrs import RETRIEVAL_BACKEND, RETRIEVAL_REQUIRED


class FakeBackend:
    """Satisfies `RetrievalBackend` with no model, index, or extra."""

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.warmups = 0
        self.calls: list[tuple[str, int, str]] = []
        self._fail = fail

    def warmup(self) -> None:
        self.warmups += 1

    def retrieve(self, query: str, k: int, strategy: str) -> RetrievalResult:
        if self._fail is not None:
            raise self._fail
        self.calls.append((query, k, strategy))
        return RetrievalResult(
            query=query,
            chunks=[
                RetrievedChunk(
                    chunk_id=f"readmission_30day::{i}",
                    doc_id="readmission_30day",
                    text="anchored on discharge",
                    score=0.9 - i / 10,
                )
                for i in range(min(k, 2))
            ],
            strategy=strategy,
            k=k,
            latency_ms=11.5,
            corpus_version="c24dc219e69d4e63",
            backend="rag_eval",
        )


# --- tool behaviour ------------------------------------------------------------


def test_search_returns_matches_with_doc_ids() -> None:
    searcher = DefinitionSearcher(FakeBackend())

    result = searcher.search("how is readmission anchored?", k=2)

    assert result.ok
    assert [m.doc_id for m in result.matches] == ["readmission_30day"] * 2
    assert result.corpus_version == "c24dc219e69d4e63"


@pytest.mark.parametrize("bad_k", [0, -1, MAX_K + 1])
def test_out_of_range_k_is_reported_not_raised(bad_k: int) -> None:
    """A bad argument should let the agent correct itself, not kill the run."""
    result = DefinitionSearcher(FakeBackend()).search("q", k=bad_k)

    assert not result.ok
    assert "k must be between" in (result.error or "")


def test_empty_query_is_reported_not_raised() -> None:
    result = DefinitionSearcher(FakeBackend()).search("   ")

    assert not result.ok
    assert "must not be empty" in (result.error or "")


def test_backend_failure_is_reported_not_raised() -> None:
    """A retrieval outage degrades the answer; it must not crash the graph."""
    searcher = DefinitionSearcher(FakeBackend(fail=RuntimeError("index corrupt")))

    result = searcher.search("q")

    assert not result.ok
    assert "index corrupt" in (result.error or "")


def test_warmup_is_delegated_once() -> None:
    backend = FakeBackend()
    searcher = DefinitionSearcher(backend)

    searcher.warmup()

    assert backend.warmups == 1


# --- span attributes -----------------------------------------------------------


def test_every_required_retrieval_attribute_is_emitted() -> None:
    """§8 + the standing rule: a capability ships with the attributes that measure it.

    Asserted against the constant set, so adding an attribute name without emitting it
    fails here rather than silently producing a metric of zero.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)

    with tracer.start_as_current_span("tool.call"):
        DefinitionSearcher(FakeBackend()).search("q", k=2)

    provider.force_flush()
    (span,) = exporter.get_finished_spans()
    assert set(span.attributes or {}) >= RETRIEVAL_REQUIRED
    assert (span.attributes or {})[RETRIEVAL_BACKEND] == "rag_eval"


def test_search_works_without_a_recording_span() -> None:
    """Telemetry must never be the reason a tool call fails."""
    trace.set_tracer_provider(trace.NoOpTracerProvider())

    assert DefinitionSearcher(FakeBackend()).search("q").ok


# --- cassette keying (§6.2) ----------------------------------------------------


class _RecordingInner:
    def __init__(self) -> None:
        self.calls = 0

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        self.calls += 1
        return ToolCallResult(tool=name, ok=True, structured={"matches": []})


def test_editing_the_corpus_invalidates_a_retrieval_cassette(tmp_path: Path) -> None:
    """The silent-wrong §6.2 exists to prevent.

    Same query, same k, EDITED corpus. Keyed on arguments alone this would replay the
    retrieval the edit was made to correct, and the cassette would look valid.
    """
    inner = _RecordingInner()
    args = {"query": "how is readmission anchored?", "k": 5}

    recorder = ReplayingMCPClient(
        inner, CassetteStore(CassetteMode.RECORD, tmp_path), corpus_version="before"
    )
    asyncio.run(recorder.call_tool("search_metric_definitions", args))
    assert inner.calls == 1

    # Same corpus: the cassette hits and the inner client is not called again.
    replayer = ReplayingMCPClient(
        None, CassetteStore(CassetteMode.REPLAY, tmp_path), corpus_version="before"
    )
    asyncio.run(replayer.call_tool("search_metric_definitions", args))
    assert inner.calls == 1

    # Edited corpus: a miss, which in REPLAY is a hard failure rather than a stale hit.
    stale = ReplayingMCPClient(
        None, CassetteStore(CassetteMode.REPLAY, tmp_path), corpus_version="after"
    )
    with pytest.raises(Exception, match="No mcp cassette"):
        asyncio.run(stale.call_tool("search_metric_definitions", args))


def test_non_corpus_tools_are_unaffected_by_corpus_version(tmp_path: Path) -> None:
    """`run_sql` does not read the dictionary, so editing it must not invalidate it."""
    inner = _RecordingInner()
    args = {"query": "SELECT 1", "max_rows": 10}

    recorder = ReplayingMCPClient(
        inner, CassetteStore(CassetteMode.RECORD, tmp_path), corpus_version="before"
    )
    asyncio.run(recorder.call_tool("run_sql", args))

    replayer = ReplayingMCPClient(
        None, CassetteStore(CassetteMode.REPLAY, tmp_path), corpus_version="after"
    )
    result = asyncio.run(replayer.call_tool("run_sql", args))

    assert result.ok
    assert inner.calls == 1


def test_corpus_dependent_tool_without_a_version_raises(tmp_path: Path) -> None:
    """Failing to supply it must be loud — a default would reintroduce the bug."""
    client = ReplayingMCPClient(
        _RecordingInner(), CassetteStore(CassetteMode.RECORD, tmp_path)
    )

    with pytest.raises(ValueError, match="corpus-dependent"):
        asyncio.run(
            client.call_tool("search_metric_definitions", {"query": "q", "k": 5})
        )
