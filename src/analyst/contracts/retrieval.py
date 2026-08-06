"""Retrieval contracts — the typed boundary around Project 1.

architecture.md §5. Project 1 returns its own `ScoredChunk` / `RetrievalResult`
dataclasses; nothing outside `analyst.retrieval` should ever see them. These models are
what crosses into the MCP tool, the span attributes, and eventually RAGAS.

`RetrievedChunk.doc_id` is the field the whole citation chain hangs on: a task's
`must_cite: [docs://metrics/readmission_30day]` is checked against it, and
`corpus_version` keys the retrieval cassette. Both are load-bearing enough that this
module refuses to construct a chunk it cannot attribute.
"""

from __future__ import annotations

from pydantic import Field

from analyst.contracts.base import Contract


class RetrievedChunk(Contract):
    """One scored passage from the metrics dictionary.

    Maps from Project 1's `ScoredChunk` — see `analyst.retrieval.rag_eval_backend`.
    `parent_id` there is typed `str | None`; `doc_id` here is not optional, because a
    citation that cannot name its document is not a citation.
    """

    chunk_id: str = Field(description="Stable id of the chunk within the corpus")
    doc_id: str = Field(description="Source document; `parent_id` upstream")
    text: str
    score: float


class RetrievalResult(Contract):
    """The result of one `search_metric_definitions` call.

    Carries the provenance the eval harness needs, not just the passages:
    `strategy` and `corpus_version` are what make a retrieval reproducible, and
    `backend` distinguishes a live retrieval from a replayed one so cassette runs and
    live runs are never conflated in the eval record (§5).
    """

    query: str
    chunks: list[RetrievedChunk]
    strategy: str
    k: int
    latency_ms: float
    corpus_version: str
    backend: str = Field(description="'rag_eval' live, or 'replay' from a cassette")

    @property
    def doc_ids(self) -> list[str]:
        """Retrieved documents, best first, de-duplicated across chunks."""
        seen: dict[str, None] = {}
        for chunk in self.chunks:
            seen.setdefault(chunk.doc_id, None)
        return list(seen)
