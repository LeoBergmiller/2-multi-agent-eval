"""`RagEvalRetriever` — Project 1's retrieval core, in process (architecture.md §5).

Uses the IN-PROCESS path only:

    load_config(path) -> load_resources(cfg)
                      -> build_retriever(strategy, cfg, resources)
                      -> retriever.retrieve(query, k) -> RetrievalResult

**Never the FastAPI `/query` endpoint.** That endpoint also runs generation, which costs
money, needs a key, and returns a prose answer when what the agent wants is passages.

`rag_eval` is imported lazily, inside `warmup()`. The `[rag]` extra is optional and CI
never installs it (D24), so importing at module scope would make
`import analyst.retrieval` fail in exactly the environment the blocking gate runs in.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from analyst.contracts import RetrievalResult, RetrievedChunk
from analyst.retrieval.corpus import corpus_version

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from rag_eval.config import Config

logger = logging.getLogger(__name__)

#: Recorded on every result so a live retrieval is distinguishable from a replayed one
#: in the eval record (§5). Replay does not go through this class at all — it is
#: intercepted at the MCP seam — so anything this class returns is live by construction.
BACKEND_NAME = "rag_eval"


class RetrievalUnavailableError(RuntimeError):
    """The `[rag]` extra or the built index is missing.

    Its own type because the fix differs per cause and both are operator errors, not
    bugs: `make install-rag` for the extra, `make index` for the index. §5 requires an
    explicit actionable message rather than an obscure ImportError.
    """


class RagEvalRetriever:
    """In-process adapter over `rag-eval`. Satisfies `RetrievalBackend`."""

    def __init__(self, config_path: Path, corpus_dir: Path | None = None) -> None:
        self._config_path = config_path
        self._explicit_corpus_dir = corpus_dir
        self._cfg: Config | None = None
        self._resources: Any = None
        self._retrievers: dict[str, Any] = {}
        self._corpus_version: str | None = None

    # -- warmup ---------------------------------------------------------------

    def warmup(self, strategy: str = "dense") -> None:
        """Load config, resources, and the retriever. Once per server process.

        Idempotent. Builds the retriever and issues one throwaway query, because the
        cost is not all in `load_resources`: `rerank` constructs its cross-encoder at
        `build_retriever` time, and the first forward pass is charged to whichever
        query runs first. Paying all of it here keeps `retrieve()` latency honest.
        """
        if self._cfg is not None and strategy in self._retrievers:
            return

        rag_eval = _import_rag_eval()

        if self._cfg is None:
            self._cfg = rag_eval["load_config"](self._config_path)
            logger.info("rag-eval config loaded from %s", self._config_path)

        if self._resources is None:
            index_dir = self._cfg.corpus.index_dir
            if not index_dir.is_dir():
                raise RetrievalUnavailableError(
                    f"No retrieval index at {index_dir}. Build it with `make index` "
                    "(needs the [rag] extra; downloads the bge model on first run)."
                )
            try:
                self._resources = rag_eval["load_resources"](self._cfg)
            except FileNotFoundError as exc:
                raise RetrievalUnavailableError(
                    f"The index at {index_dir} is incomplete ({exc}). Rebuild it with "
                    "`make index`."
                ) from exc

        if strategy not in self._retrievers:
            self._retrievers[strategy] = rag_eval["build_retriever"](
                strategy, self._cfg, self._resources
            )
            # Force the first forward pass so it is not billed to a real query.
            self._retrievers[strategy].retrieve("warmup", 1)

        logger.info("rag-eval retriever warm (strategy=%s)", strategy)

    # -- retrieve -------------------------------------------------------------

    def retrieve(self, query: str, k: int, strategy: str = "dense") -> RetrievalResult:
        """Return the `k` best-matching passages, best first."""
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")

        self.warmup(strategy)
        assert self._cfg is not None  # warmup guarantees this

        start = time.perf_counter()
        raw = self._retrievers[strategy].retrieve(query, k)
        latency_ms = (time.perf_counter() - start) * 1000

        return RetrievalResult(
            query=query,
            chunks=[_to_chunk(c) for c in raw.chunks],
            strategy=raw.strategy,
            k=k,
            # Measured here, not taken from `raw.latency_ms`: upstream times only the
            # embed + search, and what the trajectory needs is the cost of the whole
            # call. The two differ by the adapter, which is the part we own.
            latency_ms=latency_ms,
            corpus_version=self.corpus_version,
            backend=BACKEND_NAME,
        )

    @property
    def corpus_version(self) -> str:
        """Hash of the corpus this retriever is serving. Computed once."""
        if self._corpus_version is None:
            self._corpus_version = corpus_version(self._corpus_dir())
        return self._corpus_version

    def _corpus_dir(self) -> Path:
        if self._explicit_corpus_dir is not None:
            return self._explicit_corpus_dir
        if self._cfg is None:
            self.warmup()
        assert self._cfg is not None
        return Path(self._cfg.corpus.raw_dir)


def _to_chunk(scored: Any) -> RetrievedChunk:
    """Map a `rag_eval.retrieval.base.ScoredChunk` onto our contract.

    `parent_id` is typed `str | None` upstream. It RAISES here rather than defaulting,
    because `doc_id` is what `must_cite` is checked against and what a citation renders
    as — a `None` coerced to `"None"` would produce a confidently wrong citation that
    no assertion in the harness would catch. That is the Gate 0 silent-failure shape.
    """
    doc_id = getattr(scored, "parent_id", None)
    if not doc_id:
        raise ValueError(
            f"Chunk {getattr(scored, 'chunk_id', '<unknown>')!r} has no parent_id, so "
            "it cannot be attributed to a document. Every citation and every "
            "`must_cite` check is keyed on doc_id; defaulting it would produce a "
            "wrong citation instead of an error. Re-run `make index`."
        )
    return RetrievedChunk(
        chunk_id=scored.chunk_id,
        doc_id=doc_id,
        text=scored.text,
        score=scored.score,
    )


def _import_rag_eval() -> dict[str, Any]:
    """Import Project 1's in-process retrieval entry points, or explain why not."""
    try:
        from rag_eval.config import load_config
        from rag_eval.retrieval.registry import build_retriever, load_resources
    except ImportError as exc:
        raise RetrievalUnavailableError(
            "Project 1 (`rag-eval`) is not installed. It is an optional extra, "
            "deliberately absent from the default install and from CI, which run "
            "entirely from cassettes. Install it with `make install-rag`."
        ) from exc
    return {
        "load_config": load_config,
        "load_resources": load_resources,
        "build_retriever": build_retriever,
    }
