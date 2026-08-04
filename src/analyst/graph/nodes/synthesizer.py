"""Synthesizer node: AgentResults -> FinalAnswer with provenance (§3.1)."""

from __future__ import annotations

import json

from opentelemetry import trace

from analyst.contracts import AgentRole, Evidence, FinalAnswer
from analyst.graph.nodes.base import estimate_tokens, node_boundary, require
from analyst.graph.state import AnalystState, RunContext
from analyst.llm.client import LLMMessage, LLMRequest
from analyst.telemetry import attrs

ROLE = AgentRole.SYNTHESIZER

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "numeric_value": {"type": ["number", "null"]},
        "cited_refs": {"type": "array", "items": {"type": "string"}},
        "caveats": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["answer", "numeric_value", "cited_refs", "caveats", "confidence"],
    "additionalProperties": False,
}


async def synthesizer_node(state: AnalystState, ctx: RunContext) -> AnalystState:
    spec = ctx.models.roles[ROLE]
    agent = ctx.agents.roles[ROLE]
    tracer = trace.get_tracer("analyst")
    results = state.get("agent_results", {})

    with (
        tracer.start_as_current_span(attrs.SPAN_NODE) as span,
        node_boundary(ROLE) as outcome,
    ):
        span.set_attribute(attrs.MODEL_ID, spec.id)
        span.set_attribute(attrs.CASSETTE_MODE, ctx.cassette_mode)

        known_refs = {ref.ref_id for r in results.values() for ref in r.artifact_refs}

        lines = [f"Question: {state['task'].goal}", "", "Specialist results:"]
        for r in results.values():
            refs = ", ".join(ref.ref_id for ref in r.artifact_refs) or "none"
            lines.append(
                f"- subtask {r.subtask_id} [{r.status}] refs={refs}\n"
                f"  sql: {r.findings.get('executed_sql')}\n"
                f"  rows: {r.findings.get('row_count')}\n"
                f"  head: {r.findings.get('head')}\n"
                f"  assumptions: {list(r.assumptions_made) or 'none'}\n"
                f"  unresolved: {list(r.unresolved) or 'none'}"
            )
        user = "\n".join(lines)
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
                json_schema=ANSWER_SCHEMA,
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
            raw = json.loads(response.text)
        except json.JSONDecodeError as e:
            require(
                False,
                role=ROLE,
                boundary="egress",
                detail=f"Synthesizer returned invalid JSON: {e}",
            )
            raw = {}

        cited = [r for r in raw.get("cited_refs", []) if r]
        # Rule 4, checked deterministically: every citation must name a ref that
        # actually exists in this run. A fabricated citation is a groundedness
        # failure, not a formatting quirk.
        unknown = [c for c in cited if c not in known_refs]
        require(
            not unknown,
            role=ROLE,
            boundary="egress",
            detail=(
                f"Answer cites result refs that do not exist in this run: "
                f"{unknown}. Known refs: {sorted(known_refs)}"
            ),
        )
        require(
            bool(cited) or not known_refs,
            role=ROLE,
            boundary="egress",
            detail="Answer cites no evidence, but results were available.",
        )

        answer_text = raw.get("answer", "")
        final = FinalAnswer(
            answer=answer_text,
            evidence=tuple(Evidence(claim=answer_text, result_ref=c) for c in cited),
            caveats=tuple(raw.get("caveats", [])),
            confidence=float(raw.get("confidence", 0.0)),
            numeric_value=(
                float(raw["numeric_value"])
                if raw.get("numeric_value") is not None
                else None
            ),
        )
        ctx.run_dir.write_final(final)

    if not outcome.ok:
        return AnalystState(
            validation_events=[*state.get("validation_events", []), *outcome.events],
            failed=True,
        )
    return AnalystState(final=final)
