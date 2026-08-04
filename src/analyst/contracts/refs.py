"""Result references and evidence.

architecture.md §4 (critical rule) and D21: tools return a *reference* plus a
schema, row count, and `head(5)` — never the full frame. Full results live in
`runs/{run_id}/results/` and are resolved inside the sandbox. This bounds the
context window and makes `context.bundle_tokens` a measurable per-step metric.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from analyst.contracts.base import Contract

# Deliberately narrow at Gate 0: only run_sql exists, so only parquet result
# sets and json blobs can be produced. Widened with the sandbox at Gate 1.
ArtifactFormat = Literal["parquet", "json"]


class ColumnSchema(Contract):
    """One column of a result set."""

    name: str
    dtype: str


class ResultRef(Contract):
    """A pointer to a materialised result, plus just enough to reason about it.

    The invariant this type exists to enforce: an LLM may see `schema`,
    `row_count`, and `head`, and may never see the full frame. `head` is capped
    at five rows by the producer (`analyst.mcp.tools.sql`), not by this model —
    validation here would let an over-long head be silently truncated instead of
    surfacing the producer's bug.
    """

    ref_id: str = Field(description="Stable id; also the filename stem under results/")
    format: ArtifactFormat
    schema_: tuple[ColumnSchema, ...] = Field(
        alias="schema",
        description="Result set columns. Aliased because BaseModel.schema is reserved.",
    )
    row_count: int = Field(ge=0, description="Total rows materialised, not len(head)")
    head: tuple[dict[str, object], ...] = Field(
        default=(),
        description="At most 5 sample rows. NEVER the full frame — see §4.",
    )
    bytes_written: int = Field(ge=0, default=0)


class Evidence(Contract):
    """Provenance for a single claim.

    architecture.md §6.1 handoff rule 4 — "provenance or it didn't happen". An
    unattributed claim is a groundedness failure, checked deterministically.
    Exactly one of `result_ref` or `doc_id` must be set.
    """

    claim: str
    result_ref: str | None = None
    doc_id: str | None = None

    def model_post_init(self, _context: object, /) -> None:
        if (self.result_ref is None) == (self.doc_id is None):
            raise ValueError(
                "Evidence requires exactly one of result_ref or doc_id; "
                f"got result_ref={self.result_ref!r}, doc_id={self.doc_id!r}"
            )
