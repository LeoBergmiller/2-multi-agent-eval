"""SQL Analyst node: SubTask -> run_sql -> AgentResult (architecture.md §3.1).

Receives only its SubTask and the schema — no shared scratchpad, no run history
(handoff rule 1). The result it returns carries a `ResultRef`, never a frame.
"""

from __future__ import annotations

import json

from opentelemetry import trace

from analyst.contracts import AgentResult, AgentRole, ContextBundle, ResultRef
from analyst.graph.nodes.base import args_hash, estimate_tokens, node_boundary, require
from analyst.graph.state import AnalystState, RunContext
from analyst.llm.client import LLMMessage, LLMRequest
from analyst.telemetry import attrs

ROLE = AgentRole.SQL_ANALYST

SQL_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "criteria_met": {"type": "array", "items": {"type": "boolean"}},
        "confidence": {"type": "number"},
    },
    "required": ["sql", "assumptions", "criteria_met", "confidence"],
    "additionalProperties": False,
}


async def sql_analyst_node(state: AnalystState, ctx: RunContext) -> AnalystState:
    plan = state["plan"]
    spec = ctx.models.roles[ROLE]
    agent = ctx.agents.roles[ROLE]
    tracer = trace.get_tracer("analyst")

    results: dict[str, AgentResult] = dict(state.get("agent_results", {}))
    events = list(state.get("validation_events", []))

    for subtask in plan.subtasks:
        if subtask.assigned_role is not ROLE:
            continue

        with (
            tracer.start_as_current_span(attrs.SPAN_NODE) as span,
            node_boundary(ROLE, subtask.id) as outcome,
        ):
            span.set_attribute(attrs.MODEL_ID, spec.id)
            span.set_attribute(attrs.CASSETTE_MODE, ctx.cassette_mode)

            # Bounded handoff: the subtask and its criteria, nothing else.
            bundle = ContextBundle(
                goal=subtask.goal,
                constraints=subtask.acceptance_criteria,
                token_estimate=0,
            )
            user = (
                f"Subtask: {bundle.goal}\n"
                "Acceptance criteria:\n"
                + "\n".join(f"  - {c}" for c in subtask.acceptance_criteria)
                + "\n\nReturn the SQL you would run, your assumptions, whether each "
                "acceptance criterion is met (in order), and your confidence."
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
                    json_schema=SQL_SCHEMA,
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

            try:
                plan_out = json.loads(response.text)
            except json.JSONDecodeError as e:
                require(
                    False,
                    role=ROLE,
                    boundary="egress",
                    detail=f"SQL Analyst returned invalid JSON: {e}",
                    subtask_id=subtask.id,
                )
                plan_out = {}

            sql = plan_out.get("sql", "")
            require(
                bool(sql),
                role=ROLE,
                boundary="egress",
                detail="SQL Analyst returned no query.",
                subtask_id=subtask.id,
            )

            # -- the tool call ------------------------------------------------
            tool_args = {"query": sql}
            with tracer.start_as_current_span(attrs.SPAN_TOOL_CALL) as tool_span:
                tool_span.set_attribute(attrs.TOOL_NAME, "run_sql")
                tool_span.set_attribute(attrs.TOOL_ARGS_HASH, args_hash(tool_args))
                tool_span.set_attribute(attrs.AGENT_ROLE, ROLE.value)
                tool_span.set_attribute(attrs.SUBTASK_ID, subtask.id)
                tool_span.set_attribute(attrs.CASSETTE_MODE, ctx.cassette_mode)

                call = await ctx.mcp.call_tool("run_sql", tool_args)
                ctx.tool_calls.append("run_sql")

                payload = call.structured or {}
                tool_ok = bool(payload.get("ok"))
                ref_payload = payload.get("ref")
                ref = ResultRef.model_validate(ref_payload) if ref_payload else None
                if ref is not None:
                    tool_span.set_attribute(attrs.RESULT_REF, ref.ref_id)

            require(
                tool_ok and ref is not None,
                role=ROLE,
                boundary="egress",
                detail=f"run_sql rejected the query: {payload.get('error')}",
                subtask_id=subtask.id,
            )

            criteria = plan_out.get("criteria_met", [])
            confidence = float(plan_out.get("confidence", 0.0))
            assumptions = tuple(plan_out.get("assumptions", []))
            # Rule 5: a low-confidence result must name its assumptions. Supply
            # one rather than letting the contract reject the whole result.
            if confidence < 0.8 and not assumptions:
                assumptions = (
                    "Model reported low confidence but named no assumption.",
                )

            results[subtask.id] = AgentResult(
                subtask_id=subtask.id,
                status="ok",
                findings={
                    "executed_sql": payload.get("executed_sql"),
                    "head": list(ref.head) if ref else [],
                    "row_count": ref.row_count if ref else 0,
                },
                artifact_refs=(ref,) if ref else (),
                criteria_met={
                    c: bool(m)
                    for c, m in zip(subtask.acceptance_criteria, criteria, strict=False)
                },
                assumptions_made=assumptions,
                confidence=confidence,
                cost_usd=response.cost_usd,
            )

        if not outcome.ok:
            events.extend(outcome.events)
            return AnalystState(
                agent_results=results, validation_events=events, failed=True
            )

    return AnalystState(agent_results=results, validation_events=events)
