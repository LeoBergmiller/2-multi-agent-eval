"""The retrieval backend protocol (architecture.md §5).

Deliberately two methods. `warmup()` is separate from `retrieve()` because Project 1
loads a sentence-transformer model and two indexes on first use, and doing that lazily
inside the first `retrieve()` would charge one arbitrary query for the whole cost and
make every latency measurement a lie.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from analyst.contracts import RetrievalResult


@runtime_checkable
class RetrievalBackend(Protocol):
    """A source of scored passages from the metrics dictionary."""

    def warmup(self) -> None:
        """Load models and indexes. Called ONCE per server process, never per call.

        Must be idempotent: calling it twice loads nothing twice.
        """
        ...

    def retrieve(self, query: str, k: int, strategy: str) -> RetrievalResult:
        """Return the `k` best-matching passages, best first."""
        ...
