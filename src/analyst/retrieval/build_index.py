"""`make index` — build the metrics-dictionary index via Project 1's ingest pipeline.

Calls `rag_eval.ingest.pipeline.run_ingest` directly rather than shelling out to
`python -m rag_eval.cli ingest`. The CLI imports the eval harness, the generator and the
gate at module scope, so it needs the `[full]` extra; this repo installs only rag-eval's
retrieval core (D24). Calling `run_ingest` keeps that boundary intact and lets the
config path be passed explicitly instead of through the `RAG_CONFIG` environment.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from analyst.retrieval.corpus import corpus_version
from analyst.retrieval.rag_eval_backend import RetrievalUnavailableError

logger = logging.getLogger(__name__)


def build_index(config_path: Path) -> int:
    try:
        from rag_eval.config import load_config
        from rag_eval.ingest.pipeline import run_ingest
    except ImportError as exc:
        raise RetrievalUnavailableError(
            "Project 1 (`rag-eval`) is not installed. Run `make install-rag` first — "
            "it is an optional extra and CI never installs it."
        ) from exc

    cfg = load_config(config_path)
    if cfg.corpus.source != "local":
        raise ValueError(
            f"Expected corpus.source 'local' in {config_path}, got "
            f"{cfg.corpus.source!r}. This repo's corpus is authored Markdown on disk; "
            "the arXiv and PMC sources would try to download one."
        )

    manifest = run_ingest(cfg)
    version = corpus_version(cfg.corpus.raw_dir)

    logger.info(
        "Indexed %d documents into %d chunks at %s",
        manifest.n_papers,
        manifest.n_chunks,
        cfg.corpus.index_dir,
    )
    print(
        f"corpus:         {cfg.corpus.raw_dir}\n"
        f"documents:      {manifest.n_papers}\n"
        f"chunks:         {manifest.n_chunks}\n"
        f"index:          {cfg.corpus.index_dir}\n"
        f"embedding:      {manifest.embedding_model} "
        f"(dim {manifest.embedding_dimension})\n"
        f"corpus_version: {version}\n"
        "\nNOTE: corpus_version keys the retrieval cassettes. If it changed, every "
        "cassette recorded against the previous corpus is now stale and must be "
        "re-recorded (architecture.md §6.2)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/rag_eval.yaml"),
        help="rag-eval config owned by this repo",
    )
    args = parser.parse_args(argv)
    try:
        return build_index(args.config)
    except RetrievalUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
