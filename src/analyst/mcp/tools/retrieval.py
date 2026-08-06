"""`search_metric_definitions` — the metrics-dictionary lookup (architecture.md §4, §5).

An adapter over Project 1's retrieval core. **No LLM call**: this returns passages, and
the agent decides what they mean. Emits the `retrieval.*` span attributes in the same
module that performs the retrieval, per the standing rule that a capability ships with
the attributes that measure it.

Unlike `run_sql` this returns the passage TEXT rather than a `ResultRef`. That is not an
exception to D21 — the no-frames-through-context rule bounds *tabular* payloads, and a
definition the agent cannot read is useless to it. The bound here is `k`, and the
passages are short by construction.
"""

from __future__ import annotations

import logging

from opentelemetry import trace
from pydantic import Field

from analyst.contracts import Contract, RetrievalResult, RetrievedChunk
from analyst.retrieval.backend import RetrievalBackend
from analyst.telemetry.attrs import (
    RETRIEVAL_BACKEND,
    RETRIEVAL_CORPUS_VERSION,
    RETRIEVAL_DOC_IDS,
    RETRIEVAL_K,
    RETRIEVAL_LATENCY_MS,
    RETRIEVAL_SCORES,
    RETRIEVAL_STRATEGY,
)

logger = logging.getLogger(__name__)

#: Cap on `k`. Retrieval is cheap, but an unbounded k would put the whole corpus in
#: context and quietly defeat the point of measuring retrieval at all.
MAX_K = 20


class DefinitionMatch(Contract):
    """One retrieved definition, as the model sees it."""

    doc_id: str
    chunk_id: str
    text: str
    score: float

    @classmethod
    def from_chunk(cls, chunk: RetrievedChunk) -> DefinitionMatch:
        return cls(
            doc_id=chunk.doc_id,
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            score=chunk.score,
        )


class SearchResult(Contract):
    """What `search_metric_definitions` returns.

    `ok=False` is a reported failure, not an exception — same reasoning as
    `QueryResult`: a lookup that fails should let the agent adapt, not kill the run.
    """

    ok: bool
    matches: list[DefinitionMatch] = Field(default_factory=list)
    strategy: str | None = None
    corpus_version: str | None = None
    error: str | None = None
    elapsed_ms: float = 0.0


class DefinitionSearcher:
    """Runs metric-definition lookups against a `RetrievalBackend`."""

    def __init__(self, backend: RetrievalBackend, *, strategy: str = "dense") -> None:
        self._backend = backend
        self._strategy = strategy

    def warmup(self) -> None:
        """Load models and indexes once, at server startup. Never per call (§5)."""
        self._backend.warmup()

    def search(self, query: str, k: int = 5) -> SearchResult:
        if not query.strip():
            return SearchResult(ok=False, error="query must not be empty")
        if k < 1 or k > MAX_K:
            return SearchResult(ok=False, error=f"k must be between 1 and {MAX_K}")

        try:
            result = self._backend.retrieve(query, k, self._strategy)
        except Exception as exc:  # reported, never raised through MCP
            logger.warning("retrieval failed: %s", exc)
            return SearchResult(ok=False, error=str(exc))

        _record_span_attributes(result)

        return SearchResult(
            ok=True,
            matches=[DefinitionMatch.from_chunk(c) for c in result.chunks],
            strategy=result.strategy,
            corpus_version=result.corpus_version,
            elapsed_ms=result.latency_ms,
        )


def _record_span_attributes(result: RetrievalResult) -> None:
    """Attach `retrieval.*` to the current span (§5, §8).

    Silent if there is no recording span — which is the case in unit tests and when the
    tool is exercised standalone. That is deliberate: telemetry must never be the reason
    a tool call fails.
    """
    span = trace.get_current_span()
    if not span.is_recording():
        return
    span.set_attribute(RETRIEVAL_STRATEGY, result.strategy)
    span.set_attribute(RETRIEVAL_K, result.k)
    span.set_attribute(RETRIEVAL_LATENCY_MS, result.latency_ms)
    # Sequences of floats/strings are valid OTel attribute values; kept as sequences
    # rather than a joined string so the harness reads them back without parsing.
    span.set_attribute(RETRIEVAL_SCORES, [c.score for c in result.chunks])
    span.set_attribute(RETRIEVAL_DOC_IDS, result.doc_ids)
    span.set_attribute(RETRIEVAL_CORPUS_VERSION, result.corpus_version)
    span.set_attribute(RETRIEVAL_BACKEND, result.backend)
