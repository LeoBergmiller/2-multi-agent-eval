"""Graph state and the shared per-run context.

`AnalystState` is a TypedDict because that is what LangGraph merges between
nodes; every *value* in it is a typed contract, so §13's "no untyped dicts
across module boundaries" still holds — the dict is the transport, not the
payload.

Shaped for five nodes, not three. `agent_results` is keyed by subtask id and
`validation_events` is a list, so adding the Validator, Docs Analyst and Quant
Analyst at Gate 1 adds entries rather than changing the shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from opentelemetry import trace

from analyst.artifacts import RunDirectory
from analyst.contracts import (
    AgentResult,
    AgentsConfig,
    FinalAnswer,
    ModelsConfig,
    Plan,
    TaskSpec,
    ValidationEvent,
)
from analyst.llm.client import LLMClient
from analyst.mcp.client import MCPClient


class AnalystState(TypedDict, total=False):
    """What flows between nodes."""

    task: TaskSpec
    plan: Plan
    agent_results: dict[str, AgentResult]
    final: FinalAnswer
    validation_events: list[ValidationEvent]
    #: Set when the run cannot continue. At Gate 0 the router sends this to
    #: terminal; at Gate 1 the same field routes to replan.
    failed: bool


@dataclass
class RunContext:
    """Everything a node needs that is not graph state.

    Deliberately *not* in `AnalystState`: clients and file handles are not
    serialisable, and putting them in state would break the checkpointer.
    """

    task_id: str
    run_dir: RunDirectory
    #: Threaded explicitly rather than fetched from the OTel global, which can
    #: only be set once per process. See telemetry.setup.RunTracing.
    tracer: trace.Tracer
    llm: LLMClient
    mcp: MCPClient
    models: ModelsConfig
    agents: AgentsConfig
    cassette_mode: str
    #: Accumulated across the run so meta.json can report a real total (§9).
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[str] = field(default_factory=list)

    def record_usage(
        self, *, cost: float, input_tokens: int, output_tokens: int
    ) -> None:
        self.cost_usd += cost
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens


def initial_state(task: TaskSpec) -> AnalystState:
    return AnalystState(
        task=task,
        agent_results={},
        validation_events=[],
        failed=False,
    )
