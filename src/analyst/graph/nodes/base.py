"""Shared node machinery: the ingress/egress validation boundary.

architecture.md §6.1 rule 3 and §13: validation failures are **recorded events
routed onward, never unhandled exceptions**. `node_boundary` is where that is
enforced — a `ContextTransferError` raised inside is caught here and turned into
a `ValidationEvent` on state plus a span attribute.

At Gate 0 a validation failure marks the run failed and the router sends it to
terminal, because there is no Validator node and no replan edge yet. At Gate 1
the router's target changes; this boundary does not.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import trace

from analyst.contracts import (
    AgentRole,
    Boundary,
    ContextTransferError,
    ValidationEvent,
)
from analyst.telemetry import attrs


@dataclass
class BoundaryOutcome:
    """Result of running a node body inside the boundary."""

    events: list[ValidationEvent] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.events


def args_hash(payload: dict[str, Any]) -> str:
    """Stable hash of tool arguments, for the `tool.args_hash` span attribute.

    The loop and duplicate-work metrics at Gate 1 are computed from repeated
    `(tool, args_hash)` pairs, so this must be order-independent.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def estimate_tokens(text: str) -> int:
    """Rough token estimate for `context.bundle_tokens`.

    Deliberately a cheap heuristic (~4 chars/token) rather than a tokenizer
    call: this attribute exists to show a handoff is *bounded* and to let the
    bound be compared across runs, not to bill anyone. A real tokenizer here
    would add an API round-trip per handoff for no gain in what it measures.
    """
    return max(1, len(text) // 4)


@contextmanager
def node_boundary(
    role: AgentRole, subtask_id: str | None = None
) -> Iterator[BoundaryOutcome]:
    """Run a node body, converting boundary violations into recorded events."""
    outcome = BoundaryOutcome()
    span = trace.get_current_span()
    span.set_attribute(attrs.AGENT_ROLE, role.value)
    if subtask_id:
        span.set_attribute(attrs.SUBTASK_ID, subtask_id)

    try:
        yield outcome
    except ContextTransferError as e:
        # The whole point of rule 3: this does not propagate.
        outcome.events.append(e.as_event())

    span.set_attribute(attrs.VALIDATION_PASSED, outcome.ok)
    for event in outcome.events:
        span.add_event(
            "validation.failed",
            {
                "boundary": event.boundary,
                "detail": event.detail,
                "role": event.role.value,
            },
        )


def require(
    condition: bool,
    *,
    role: AgentRole,
    boundary: Boundary,
    detail: str,
    subtask_id: str | None = None,
) -> None:
    """Assert a boundary condition, raising the catchable transfer error."""
    if not condition:
        raise ContextTransferError(
            role=role, boundary=boundary, detail=detail, subtask_id=subtask_id
        )
