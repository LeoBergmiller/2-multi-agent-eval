"""LLM client — cassette seam 1 (architecture.md §6.2).

Every model call in the system goes through `LLMClient.complete`. That single
choke point is what the cassette interceptor wraps, and it is why the graph
nodes never import `anthropic` directly.

Two API facts shape this module, both verified against the current models rather
than recalled:

* `temperature`, `top_p` and `top_k` are **rejected with a 400** on Opus 5 and
  Sonnet 5. There is therefore no determinism knob here. Determinism comes from
  cassette replay; the live arm uses n=3 and a tolerance band (§7.5, corrected).
* `max_tokens` caps thinking **and** response text together, and thinking is on
  by default on Opus 5. Budgets in `config/models.yaml` account for that.

Cost is computed here, from the price table in `config/models.yaml`, because §9
requires cost measured rather than estimated.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from analyst.contracts import AgentRole, Contract, ModelsConfig


class LLMMessage(Contract):
    """One conversational turn. Only `user`/`assistant` — the system prompt is
    a separate field, as the API requires."""

    role: str
    content: str


class LLMRequest(Contract):
    """A model call, in a form that hashes stably for cassette keying."""

    agent_role: AgentRole
    model: str
    system: str
    messages: tuple[LLMMessage, ...]
    max_tokens: int
    effort: str
    json_schema: dict[str, Any] | None = None


class LLMResponse(Contract):
    """A model reply plus the usage needed to price it."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    stop_reason: str | None = None


@runtime_checkable
class LLMClient(Protocol):
    """The seam. The live client and the replay interceptor both satisfy it."""

    async def complete(self, request: LLMRequest) -> LLMResponse: ...


class AnthropicLLMClient:
    """Live Anthropic client. Only constructed for RECORD and LIVE runs."""

    def __init__(self, models: ModelsConfig) -> None:
        # Imported lazily so a REPLAY run never needs the SDK's client
        # constructed, and never needs an API key present.
        from anthropic import AsyncAnthropic

        self._models = models
        self._client = AsyncAnthropic()

    async def complete(self, request: LLMRequest) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
            "output_config": {"effort": request.effort},
        }
        if request.json_schema is not None:
            kwargs["output_config"] = {
                "effort": request.effort,
                "format": {"type": "json_schema", "schema": request.json_schema},
            }

        message = await self._client.messages.create(**kwargs)

        text = "".join(
            block.text
            for block in message.content
            if getattr(block, "type", "") == "text"
        )
        usage = message.usage
        spec = self._models.roles[request.agent_role]
        return LLMResponse(
            text=text,
            model=message.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=spec.cost_usd(
                input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
            ),
            stop_reason=message.stop_reason,
        )
