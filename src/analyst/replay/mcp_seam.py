"""Cassette interceptor for the MCP client (seam 2 of 2).

Note how little there is here. That is the payoff of intercepting at the client
rather than per tool: `run_sql` today, `run_python` and
`search_metric_definitions` at Gate 1, all covered by this one class because
they are all MCP tool calls (D16).
"""

from __future__ import annotations

from typing import Any

from analyst.mcp.client import MCPClient, ToolCallResult
from analyst.replay.store import CassetteStore, Seam


class ReplayingMCPClient:
    """Wraps an `MCPClient`, recording or replaying at the tool-call boundary.

    In REPLAY the inner client is None, so no server subprocess is spawned and
    the warehouse is never opened. A replay run therefore needs no DuckDB file —
    only the committed cassettes.

    One consequence worth knowing: a replayed run's `results/` directory is
    empty, because the recorded artefact is the `ResultRef`, not the Parquet
    frame behind it. Recording the frame would mean a third seam, which §6.2
    forbids. Nothing at Gate 0 resolves a ref to its file, and the committed
    demo run is a RECORD run, so it carries real results.
    """

    SEAM: Seam = "mcp"

    def __init__(self, inner: MCPClient | None, store: CassetteStore) -> None:
        self._inner = inner
        self._store = store

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        payload = {"tool": name, "arguments": arguments}

        cached = self._store.load(self.SEAM, payload)
        if cached is not None:
            return ToolCallResult.model_validate(cached)

        if self._inner is None:
            raise RuntimeError(
                "No live MCP client available and no cassette matched. This "
                "should be unreachable: REPLAY raises CassetteMiss before here."
            )

        result = await self._inner.call_tool(name, arguments)
        self._store.save(self.SEAM, payload, result.model_dump(mode="json"))
        return result
