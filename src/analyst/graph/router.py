"""Deterministic dispatch (architecture.md §3.1).

No model call decides routing. The topology is a supervisor tree precisely so
failures are attributable and a reference trajectory is definable (D7) — a
router that asked an LLM where to go next would give that up.

The Gate 0 / Gate 1 seam lives here. `route_after` returns `TERMINAL` on a
validation failure today; at Gate 1 that target becomes the replan edge back to
the Planner. The node boundary that produces the event does not change — only
this mapping does.
"""

from __future__ import annotations

from typing import Final, Literal

from analyst.contracts import AgentRole
from analyst.graph.state import AnalystState

TERMINAL: Final = "__end__"

NodeName = Literal["planner", "sql_analyst", "synthesizer", "__end__"]

#: Node order for the Gate 0 path. Validator, Docs Analyst and Quant Analyst
#: are absent rather than stubbed — see §10.
GATE0_SEQUENCE: Final[tuple[NodeName, ...]] = ("planner", "sql_analyst", "synthesizer")


def route_after(current: NodeName, state: AnalystState) -> NodeName:
    """Where to go after `current`."""
    if state.get("failed"):
        # Gate 1: return "planner" here (replan), gated on
        # ValidationEvent.recoverable and a retry budget.
        return TERMINAL

    index = GATE0_SEQUENCE.index(current)
    if index + 1 < len(GATE0_SEQUENCE):
        return GATE0_SEQUENCE[index + 1]
    return TERMINAL


def roles_in_plan(state: AnalystState) -> set[AgentRole]:
    plan = state.get("plan")
    if plan is None:
        return set()
    return {s.assigned_role for s in plan.subtasks}
