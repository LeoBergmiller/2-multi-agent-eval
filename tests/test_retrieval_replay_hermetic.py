"""Retrieval replays from committed cassettes with no index and no `[rag]` extra.

The durable form of the Gate 1a step-1 proof. It was demonstrated once by recording
through a real stdio subprocess and then deleting `data/index/`; this test is what keeps
it true, and it is the shape CI runs in — no Project 1, no model, no network.

If this ever starts needing an index or the extra, the retrieval path has leaked out of
the replay layer, which is exactly the leak §6.2's two-seam rule exists to prevent.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from analyst.replay import CassetteStore, ReplayingMCPClient
from analyst.replay.store import CassetteMode
from analyst.retrieval import corpus_version

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "data" / "metrics_dictionary"
CASSETTES = REPO_ROOT / "cassettes"

#: Recorded live through a stdio subprocess against the committed corpus.
RECORDED = [
    ("is the 30-day readmission window anchored on discharge or admission?", 3),
    ("how is length of stay counted?", 3),
    ("which encounter classes count as an admission?", 3),
]


def _replay_client() -> ReplayingMCPClient:
    """inner=None: no subprocess is spawnable, so a leak fails rather than passes."""
    return ReplayingMCPClient(
        None,
        CassetteStore(CassetteMode.REPLAY, CASSETTES),
        corpus_version=corpus_version(CORPUS),
    )


@pytest.mark.integration
@pytest.mark.parametrize(("query", "k"), RECORDED)
def test_retrieval_replays_without_index_or_extra(query: str, k: int) -> None:
    client = _replay_client()

    result = asyncio.run(
        client.call_tool("search_metric_definitions", {"query": query, "k": k})
    )

    assert result.ok
    matches = (result.structured or {})["matches"]
    assert len(matches) == k
    assert all(m["doc_id"] for m in matches)


@pytest.mark.integration
def test_replayed_retrieval_never_imports_rag_eval() -> None:
    """The claim `make demo` rests on: a replayed run needs no Project 1 at all.

    Asserted on `sys.modules` rather than on the install, so it holds whether or not
    the developer running the suite happens to have `make install-rag`-ed.
    """
    import sys

    sys.modules.pop("rag_eval", None)
    query, k = RECORDED[0]

    asyncio.run(
        _replay_client().call_tool(
            "search_metric_definitions", {"query": query, "k": k}
        )
    )

    assert "rag_eval" not in sys.modules


@pytest.mark.integration
def test_top_hit_is_the_intended_document() -> None:
    """Guards the corpus, not the model: each seed query must find its own definition.

    Cheap regression cover for step 4 — if authoring the real dictionary makes one of
    these ambiguous, that is worth knowing at authoring time rather than at eval time.
    """
    expected = {
        RECORDED[0][0]: "readmission_30day",
        RECORDED[1][0]: "length_of_stay",
        RECORDED[2][0]: "admission",
    }
    client = _replay_client()

    for query, doc_id in expected.items():
        result = asyncio.run(
            client.call_tool("search_metric_definitions", {"query": query, "k": 3})
        )
        matches = (result.structured or {})["matches"]
        assert matches[0]["doc_id"] == doc_id, f"{query!r} -> {matches[0]['doc_id']}"
