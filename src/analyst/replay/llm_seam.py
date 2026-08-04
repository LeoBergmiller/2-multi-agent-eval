"""Cassette interceptor for the LLM client (seam 1 of 2)."""

from __future__ import annotations

from analyst.contracts import ModelsConfig
from analyst.llm.client import LLMClient, LLMRequest, LLMResponse
from analyst.replay.store import CassetteMode, CassetteStore, Seam


class ReplayingLLMClient:
    """Wraps an `LLMClient`, recording or replaying at the request boundary.

    In REPLAY the inner client is never constructed (see `build_llm_client`), so
    a replay run needs neither an API key nor the network.

    Recorded usage is replayed too, which is what lets a REPLAY run report a
    real `cost.usd` rather than zero — the cost of the run that was recorded.
    """

    SEAM: Seam = "llm"

    def __init__(self, inner: LLMClient | None, store: CassetteStore) -> None:
        self._inner = inner
        self._store = store

    async def complete(self, request: LLMRequest) -> LLMResponse:
        payload = request.model_dump(mode="json")

        cached = self._store.load(self.SEAM, payload)
        if cached is not None:
            return LLMResponse.model_validate(cached)

        if self._inner is None:
            raise RuntimeError(
                "No live LLM client available and no cassette matched. This "
                "should be unreachable: REPLAY raises CassetteMiss before here."
            )

        response = await self._inner.complete(request)
        self._store.save(self.SEAM, payload, response.model_dump(mode="json"))
        return response


def build_llm_client(store: CassetteStore, models: ModelsConfig) -> ReplayingLLMClient:
    """Construct the seam, creating a live client only when one is needed.

    The `AsyncAnthropic` constructor is only reached in LIVE and RECORD. That is
    what makes a REPLAY run work with `ANTHROPIC_API_KEY` unset — the §12
    definition of done.
    """
    inner: LLMClient | None = None
    if store.mode is not CassetteMode.REPLAY:
        from analyst.llm.client import AnthropicLLMClient

        inner = AnthropicLLMClient(models)
    return ReplayingLLMClient(inner, store)
