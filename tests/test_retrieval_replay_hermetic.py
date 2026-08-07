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
def test_intended_document_is_retrieved_within_k() -> None:
    """Guards the corpus: each seed query must *retrieve* its own definition.

    Asserts **recall, not rank**. An earlier version required the intended document to
    be rank 1, which passed trivially against the three-document spike corpus and would
    now fail — because step 4's near-miss distractors deliberately outrank it on some
    queries (`length_of_stay_calendar_days` beats `length_of_stay` on a bare "how is
    length of stay counted"). That is the corpus working as designed: with retrieval
    trivially perfect, RAGAS measures nothing and the task tests nothing.

    Recall is the property that must hold. A definition the agent never sees makes a
    task unanswerable rather than hard, and an unanswerable task measures nothing
    either. Rank is what the eval is *for* — asserting it here would freeze the
    difficulty the eval exists to observe. See D27.
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
        docs = [m["doc_id"] for m in (result.structured or {})["matches"]]
        assert doc_id in docs, f"{query!r} did not retrieve {doc_id}: got {docs}"
