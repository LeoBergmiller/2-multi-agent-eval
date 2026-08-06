"""Retrieval over the metrics dictionary (architecture.md §5).

The seam around Project 1. `RetrievalBackend` mirrors `SandboxBackend`: one protocol,
one real implementation, and replay handled at the MCP seam rather than by a recorded
backend — there are two cassette seams and this is not one of them (§6.2).
"""

from analyst.retrieval.backend import RetrievalBackend
from analyst.retrieval.corpus import corpus_version

__all__ = ["RetrievalBackend", "corpus_version"]
