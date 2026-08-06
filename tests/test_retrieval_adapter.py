"""The Project 1 retrieval adapter (architecture.md §5, D24).

These tests never load a model or an index. The adapter's job is *mapping and
attribution*, and that is what is worth testing hard — a fake stands in for rag-eval's
`ScoredChunk`, exactly as a real one would arrive.

The one thing deliberately NOT tested here is that rag-eval retrieves well. That is
Project 1's own suite, and duplicating it would couple this gate to a model download.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from analyst.contracts import RetrievalResult, RetrievedChunk
from analyst.retrieval import RetrievalBackend, corpus_version
from analyst.retrieval.rag_eval_backend import (
    RetrievalUnavailableError,
    _to_chunk,
)


@dataclass
class FakeScoredChunk:
    """Shaped like `rag_eval.retrieval.base.ScoredChunk`, including optional parent."""

    chunk_id: str
    text: str
    score: float
    parent_id: str | None = None


# --- field mapping -------------------------------------------------------------


def test_parent_id_maps_to_doc_id() -> None:
    chunk = _to_chunk(
        FakeScoredChunk(
            chunk_id="readmission_30day::0",
            text="anchored on discharge",
            score=0.82,
            parent_id="readmission_30day",
        )
    )

    assert chunk.doc_id == "readmission_30day"
    assert chunk.chunk_id == "readmission_30day::0"
    assert chunk.score == 0.82


@pytest.mark.parametrize("missing", [None, ""])
def test_missing_parent_id_raises_rather_than_defaulting(missing: str | None) -> None:
    """The silent-wrong this adapter exists to prevent.

    `doc_id` is what `must_cite` is checked against and what a citation renders as. A
    `None` coerced to the string "None" would produce a confident, wrong citation that
    no assertion in the harness would catch — the Gate 0 failure shape exactly.
    """
    with pytest.raises(ValueError, match="cannot be attributed"):
        _to_chunk(
            FakeScoredChunk(
                chunk_id="orphan::0", text="t", score=0.5, parent_id=missing
            )
        )


# --- contract round-tripping ---------------------------------------------------


def test_result_survives_a_dump_load_round_trip() -> None:
    """Gate 0's first defect was a contract that only ever got dumped, never loaded.

    This one crosses the MCP seam and lands in a cassette, so it is dumped in one
    process and loaded in another. Exercise both halves together or neither fails.
    """
    result = RetrievalResult(
        query="how is length of stay counted?",
        chunks=[
            RetrievedChunk(
                chunk_id="length_of_stay::0",
                doc_id="length_of_stay",
                text="counted in midnights",
                score=0.91,
            )
        ],
        strategy="dense",
        k=5,
        latency_ms=12.5,
        corpus_version="c24dc219e69d4e63",
        backend="rag_eval",
    )

    restored = RetrievalResult.model_validate_json(result.model_dump_json())

    assert restored == result
    assert restored.chunks[0].doc_id == "length_of_stay"


def test_result_rejects_unknown_fields() -> None:
    """`extra="forbid"`: a producer adding a field no consumer reads must not pass."""
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        RetrievedChunk.model_validate(
            {
                "chunk_id": "a::0",
                "doc_id": "a",
                "text": "t",
                "score": 0.1,
                "relevance": 0.9,
            }
        )


def test_doc_ids_are_ordered_and_deduplicated() -> None:
    """Several chunks of one document cite that document once, best-first."""
    result = RetrievalResult(
        query="q",
        chunks=[
            RetrievedChunk(chunk_id="a::1", doc_id="a", text="t", score=0.9),
            RetrievedChunk(chunk_id="b::0", doc_id="b", text="t", score=0.8),
            RetrievedChunk(chunk_id="a::0", doc_id="a", text="t", score=0.7),
        ],
        strategy="dense",
        k=3,
        latency_ms=1.0,
        corpus_version="v",
        backend="rag_eval",
    )

    assert result.doc_ids == ["a", "b"]


# --- corpus_version ------------------------------------------------------------


def _corpus(root: Path, **docs: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, body in docs.items():
        (root / f"{name}.md").write_text(body)
    return root


def test_corpus_version_is_stable_for_identical_content(tmp_path: Path) -> None:
    a = _corpus(tmp_path / "a", readmission="anchored on discharge", los="midnights")
    b = _corpus(tmp_path / "b", readmission="anchored on discharge", los="midnights")

    assert corpus_version(a) == corpus_version(b)


def test_editing_a_definition_changes_corpus_version(tmp_path: Path) -> None:
    """The invalidation mechanism: a corrected definition must not replay the old."""
    corpus = _corpus(tmp_path / "c", readmission="anchored on discharge")
    before = corpus_version(corpus)

    (corpus / "readmission.md").write_text("anchored on admission")

    assert corpus_version(corpus) != before


def test_renaming_a_document_changes_corpus_version(tmp_path: Path) -> None:
    """A rename changes doc_id, so it changes every citation pointing at it."""
    corpus = _corpus(tmp_path / "c", readmission_30day="anchored on discharge")
    before = corpus_version(corpus)

    (corpus / "readmission_30day.md").rename(corpus / "readmission_30_day.md")

    assert corpus_version(corpus) != before


def test_corpus_version_ignores_non_corpus_files(tmp_path: Path) -> None:
    """The index is gitignored and rebuilt per machine; a rebuilt float must not
    invalidate cassettes. Only the words count."""
    corpus = _corpus(tmp_path / "c", readmission="anchored on discharge")
    before = corpus_version(corpus)

    (corpus / "dense.faiss").write_bytes(b"\x00\x01\x02")
    (corpus / "notes.json").write_text("{}")

    assert corpus_version(corpus) == before


def test_absent_corpus_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="corpus not found"):
        corpus_version(tmp_path / "nope")


def test_empty_corpus_raises(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match=r"No .* documents"):
        corpus_version(tmp_path / "empty")


# --- the committed corpus ------------------------------------------------------


def test_committed_corpus_hashes(committed_corpus: Path) -> None:
    """Guards the real corpus dir: present, non-empty, and hashable."""
    version = corpus_version(committed_corpus)

    assert len(version) == 16


# --- protocol conformance ------------------------------------------------------


def test_rag_eval_retriever_satisfies_the_backend_protocol() -> None:
    """Structural check only — importing the class must not import rag-eval.

    The `[rag]` extra is optional and CI never installs it, so `import
    analyst.retrieval.rag_eval_backend` has to work without it. If rag-eval were
    imported at module scope this test would fail in CI and nowhere else.
    """
    from analyst.retrieval.rag_eval_backend import RagEvalRetriever

    assert isinstance(RagEvalRetriever(Path("config/rag_eval.yaml")), RetrievalBackend)


def test_retrieve_rejects_non_positive_k() -> None:
    from analyst.retrieval.rag_eval_backend import RagEvalRetriever

    with pytest.raises(ValueError, match="k must be positive"):
        RagEvalRetriever(Path("config/rag_eval.yaml")).retrieve("q", 0)


def test_missing_extra_raises_an_actionable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§5: fail with an explicit actionable message, never an obscure import error.

    Simulates the extra being absent, which is the state CI runs in — so this asserts
    the message a stranger actually hits, not one only reachable by uninstalling.
    """
    from analyst.retrieval.rag_eval_backend import RagEvalRetriever

    def _absent() -> dict[str, object]:
        raise RetrievalUnavailableError(
            "Project 1 (`rag-eval`) is not installed. Install it with "
            "`make install-rag`."
        )

    monkeypatch.setattr("analyst.retrieval.rag_eval_backend._import_rag_eval", _absent)

    with pytest.raises(RetrievalUnavailableError, match="make install-rag"):
        RagEvalRetriever(tmp_path / "cfg.yaml").warmup()


def test_missing_index_raises_an_actionable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other operator error: extra installed, index never built."""
    from analyst.retrieval.rag_eval_backend import RagEvalRetriever

    class _Corpus:
        index_dir = tmp_path / "no-such-index"
        raw_dir = tmp_path / "corpus"

    class _Cfg:
        corpus = _Corpus()

    monkeypatch.setattr(
        "analyst.retrieval.rag_eval_backend._import_rag_eval",
        lambda: {
            "load_config": lambda _path: _Cfg(),
            "load_resources": lambda _cfg: pytest.fail("must not load a missing index"),
            "build_retriever": lambda *_a: pytest.fail("must not build a retriever"),
        },
    )

    with pytest.raises(RetrievalUnavailableError, match="make index"):
        RagEvalRetriever(tmp_path / "cfg.yaml").warmup()
