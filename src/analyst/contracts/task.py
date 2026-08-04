"""Task, plan, and handoff contracts.

Shapes follow architecture.md §6.1. Gate 0 exercises three of the five roles;
`AgentRole` names all five so the enum does not change when the remaining nodes
land at Gate 1 (§10 — five nodes, do not add a sixth).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from analyst.contracts.base import Contract
from analyst.contracts.refs import ResultRef


class AgentRole(StrEnum):
    """The five nodes. Do not add a sixth (architecture.md §3.1, §13)."""

    PLANNER = "planner"
    SQL_ANALYST = "sql_analyst"
    DOCS_ANALYST = "docs_analyst"  # Gate 1
    QUANT_ANALYST = "quant_analyst"  # Gate 1
    SYNTHESIZER = "synthesizer"


#: Roles with a node implementation at Gate 0. The router rejects a Plan that
#: assigns work to an unbuilt role rather than failing at dispatch time.
GATE0_ROLES: frozenset[AgentRole] = frozenset(
    {AgentRole.PLANNER, AgentRole.SQL_ANALYST, AgentRole.SYNTHESIZER}
)


class TaskSpec(Contract):
    """The unit of work handed to the graph."""

    goal: str
    constraints: tuple[str, ...] = ()
    max_steps: int = Field(default=20, gt=0)
    max_usd: float = Field(default=0.50, gt=0, description="Run-level killswitch (§9)")


class SubTask(Contract):
    """One unit of delegated work.

    `acceptance_criteria` is required and travels with the subtask — handoff
    rule 2 (§6.1). The specialist self-reports against it in
    `AgentResult.criteria_met`, which is what makes silent under-delivery
    detectable without an LLM judge.
    """

    id: str
    goal: str
    assigned_role: AgentRole
    input_refs: tuple[ResultRef, ...] = ()
    acceptance_criteria: tuple[str, ...] = Field(min_length=1)
    depends_on: tuple[str, ...] = ()


class Plan(Contract):
    """A DAG of subtasks emitted by the Planner."""

    subtasks: tuple[SubTask, ...] = Field(min_length=1)
    edges: tuple[tuple[str, str], ...] = ()
    expected_tool_sequence: tuple[str, ...] = Field(
        default=(),
        description="Seeds the reference trajectory (§7.2). Not scored at Gate 0.",
    )

    @model_validator(mode="after")
    def _check_referential_integrity(self) -> Plan:
        ids = {s.id for s in self.subtasks}
        if len(ids) != len(self.subtasks):
            raise ValueError("SubTask ids must be unique within a Plan")
        for src, dst in self.edges:
            if src not in ids or dst not in ids:
                raise ValueError(f"Plan edge ({src!r}, {dst!r}) references unknown id")
        for sub in self.subtasks:
            for dep in sub.depends_on:
                if dep not in ids:
                    raise ValueError(
                        f"SubTask {sub.id!r} depends_on unknown id {dep!r}"
                    )
        return self


class ContextBundle(Contract):
    """The bounded context a specialist receives. Never the full run history.

    Handoff rule 1 (§6.1): no shared scratchpad. A specialist gets its SubTask,
    its input refs, and nothing else — passing everything to everyone is just a
    slower single agent.

    `token_estimate` is emitted as the `context.bundle_tokens` span attribute,
    which is what makes the bounded-handoff rule measurable rather than merely
    asserted.
    """

    goal: str
    constraints: tuple[str, ...] = ()
    input_refs: tuple[ResultRef, ...] = ()
    token_estimate: int = Field(ge=0, default=0)


class Handoff(Contract):
    """A typed transfer between two nodes."""

    from_role: AgentRole
    to_role: AgentRole
    subtask: SubTask
    context_bundle: ContextBundle
    provenance: tuple[str, ...] = ()
