"""Planner node: TaskSpec -> Plan (architecture.md §3.1)."""

from __future__ import annotations

import json

from analyst.contracts import GATE0_ROLES, AgentRole, Plan, SubTask
from analyst.graph.nodes.base import estimate_tokens, node_boundary, require
from analyst.graph.state import AnalystState, RunContext
from analyst.llm.client import LLMMessage, LLMRequest
from analyst.telemetry import attrs

ROLE = AgentRole.PLANNER

#: Schema handed to the model as a structured-output constraint. Narrower than
#: the full `Plan` contract on purpose: the model should not be inventing
#: `input_refs` or `expected_tool_sequence` before anything has run.
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "subtasks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "goal": {"type": "string"},
                    "assigned_role": {"type": "string", "enum": ["sql_analyst"]},
                    "acceptance_criteria": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                },
                "required": ["id", "goal", "assigned_role", "acceptance_criteria"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["subtasks"],
    "additionalProperties": False,
}


async def planner_node(state: AnalystState, ctx: RunContext) -> AnalystState:
    task = state["task"]
    spec = ctx.models.roles[ROLE]
    agent = ctx.agents.roles[ROLE]

    tracer = ctx.tracer
    with (
        tracer.start_as_current_span(attrs.SPAN_NODE) as span,
        node_boundary(ROLE) as outcome,
    ):
        span.set_attribute(attrs.MODEL_ID, spec.id)
        span.set_attribute(attrs.CASSETTE_MODE, ctx.cassette_mode)

        user = (
            f"Goal: {task.goal}\n"
            f"Constraints: {'; '.join(task.constraints) or 'none'}\n"
            f"Budget: at most {task.max_steps} steps."
        )
        span.set_attribute(
            attrs.CONTEXT_BUNDLE_TOKENS, estimate_tokens(agent.prompt + user)
        )

        response = await ctx.llm.complete(
            LLMRequest(
                agent_role=ROLE,
                model=spec.id,
                system=agent.prompt,
                messages=(LLMMessage(role="user", content=user),),
                max_tokens=spec.max_tokens,
                effort=spec.effort,
                json_schema=PLAN_SCHEMA,
            )
        )
        ctx.record_usage(
            cost=response.cost_usd,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        span.set_attribute(attrs.COST_USD, response.cost_usd)
        span.set_attribute(attrs.GEN_AI_USAGE_INPUT_TOKENS, response.input_tokens)
        span.set_attribute(attrs.GEN_AI_USAGE_OUTPUT_TOKENS, response.output_tokens)

        # -- egress validation ------------------------------------------------
        try:
            raw = json.loads(response.text)
        except json.JSONDecodeError as e:
            require(
                False,
                role=ROLE,
                boundary="egress",
                detail=f"Planner did not return valid JSON: {e}",
            )
            raw = {}

        subtasks = []
        for item in raw.get("subtasks", []):
            role_value = item.get("assigned_role", "")
            require(
                role_value in {r.value for r in GATE0_ROLES},
                role=ROLE,
                boundary="egress",
                detail=(
                    f"Plan assigns work to {role_value!r}, which has no node at "
                    f"Gate 0. Buildable roles: {sorted(r.value for r in GATE0_ROLES)}"
                ),
            )
            subtasks.append(
                SubTask(
                    id=item["id"],
                    goal=item["goal"],
                    assigned_role=AgentRole(role_value),
                    acceptance_criteria=tuple(item["acceptance_criteria"]),
                )
            )

        require(
            bool(subtasks),
            role=ROLE,
            boundary="egress",
            detail="Planner produced an empty plan.",
        )

        plan = Plan(subtasks=tuple(subtasks))
        ctx.run_dir.write_plan(plan)

    if not outcome.ok:
        return AnalystState(
            validation_events=[*state.get("validation_events", []), *outcome.events],
            failed=True,
        )
    return AnalystState(plan=plan)
