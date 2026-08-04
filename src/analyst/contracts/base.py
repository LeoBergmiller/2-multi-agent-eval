"""Shared base for every inter-node contract.

architecture.md §13: no node may emit or accept an untyped dict. Every object
that crosses a module boundary inherits from `Contract`, which is frozen and
rejects unknown fields — so a shape mismatch fails at the boundary that
introduced it rather than three nodes downstream.
"""

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    """Frozen, strictly-validated base for all inter-node payloads.

    `extra="forbid"` is the load-bearing setting. Pydantic's default silently
    drops unknown keys, which would let a producer add a field, a consumer never
    read it, and the mismatch go unnoticed until it shows up as a wrong answer.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        # Aliased fields (ResultRef.schema_ / "schema") must survive a
        # dump -> load round trip. Without this, `model_dump_json()` emits the
        # field name while validation accepts only the alias, so a contract
        # whose entire job is crossing boundaries could not be read back.
        populate_by_name=True,
    )
