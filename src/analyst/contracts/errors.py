"""Validation failures as first-class recorded events.

architecture.md §6.1 rule 3 and §13: validation failures at a node boundary are
**recorded events routed to replan, never unhandled exceptions**.

The mechanism is deliberately two-part:

* `ContextTransferError` is raised *inside* a node's ingress/egress boundary and
  is always caught by that boundary. It never escapes into the graph.
* `ValidationEvent` is the typed record the boundary produces instead. It lands
  in graph state and on the span, and the router dispatches on it.

At Gate 0 the router sends a `ValidationEvent` to terminal failure, because
there is no Validator node and no replan edge yet. At Gate 1 the same event
routes to replan — a change of edge target, not of mechanism. Building it this
way now is what stops "raise and see what happens" from becoming the habit.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from analyst.contracts.base import Contract
from analyst.contracts.task import AgentRole

#: Which side of a node boundary rejected the payload.
Boundary = Literal["ingress", "egress"]


class ContextTransferError(Exception):
    """Raised at a node boundary when a payload fails validation.

    Caught by the boundary that raised it and converted to a `ValidationEvent`.
    If this ever propagates out of a node, that is a bug in the node wrapper,
    not an expected failure mode.
    """

    def __init__(
        self,
        *,
        role: AgentRole,
        boundary: Boundary,
        detail: str,
        subtask_id: str | None = None,
    ) -> None:
        self.role = role
        self.boundary = boundary
        self.detail = detail
        self.subtask_id = subtask_id
        super().__init__(f"{role.value} {boundary} validation failed: {detail}")

    def as_event(self) -> ValidationEvent:
        return ValidationEvent(
            role=self.role,
            boundary=self.boundary,
            detail=self.detail,
            subtask_id=self.subtask_id,
        )


class ValidationEvent(Contract):
    """A recorded validation failure. Carried in state, emitted on the span."""

    role: AgentRole
    boundary: Boundary
    detail: str
    subtask_id: str | None = None
    recoverable: bool = Field(
        default=True,
        description=(
            "Whether a replan could plausibly fix this. Unused at Gate 0 (all "
            "failures terminate); consumed by the replan edge at Gate 1."
        ),
    )
