"""`corpus_version` — the hash that invalidates stale retrieval cassettes.

architecture.md §6.2: the retrieval cassette key includes
`normalized_query + k + strategy + corpus_version`, where `corpus_version` hashes the
metrics-dictionary contents. Editing a definition must invalidate every cassette
recorded against the old wording — otherwise a corrected definition silently replays
the retrieval it was corrected away from, and the eval scores a corpus that no longer
exists.

Hashing the corpus SOURCE, not the built index: the index is gitignored and rebuilt per
machine, and a rebuild that changes a float in a FAISS file must not invalidate
cassettes. What matters is whether the words changed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Extensions ingested by rag-eval's `local` source. Kept in step with it deliberately:
#: hashing a file the indexer ignores (or ignoring one it reads) would decouple the
#: cassette key from what was actually retrieved.
CORPUS_SUFFIXES = (".md", ".txt")


def corpus_version(corpus_dir: Path) -> str:
    """Stable 16-char digest of every document in `corpus_dir`.

    Covers document *names* as well as bodies, so renaming a file — which changes its
    `doc_id`, and therefore every citation pointing at it — also changes the version.
    """
    if not corpus_dir.is_dir():
        raise FileNotFoundError(
            f"Metrics-dictionary corpus not found at {corpus_dir}. `corpus_version` "
            "keys the retrieval cassettes, so it cannot be computed from an absent "
            "corpus without silently making every cassette look valid."
        )

    paths = sorted(
        p for p in corpus_dir.rglob("*") if p.suffix.lower() in CORPUS_SUFFIXES
    )
    if not paths:
        raise FileNotFoundError(
            f"No {' / '.join(CORPUS_SUFFIXES)} documents under {corpus_dir}. An empty "
            "corpus hashes to a stable value and would key cassettes that retrieve "
            "nothing."
        )

    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(corpus_dir).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]
