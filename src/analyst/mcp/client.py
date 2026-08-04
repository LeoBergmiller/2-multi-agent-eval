"""MCP client — cassette seam 2 (architecture.md §6.2).

Everything the graph does through MCP goes through `MCPClient.call_tool`. That
single choke point is why one interceptor covers `run_sql`, and later
`run_python` and `search_metric_definitions` too: they are all MCP tools, so
there is no need for a bespoke recorder per tool (D16).

Two implementations:

* `StdioMCPClient` spawns the server as a subprocess and speaks stdio, which is
  what §4 specifies for local dev and CI.
* `InProcessMCPClient` binds a server object directly, with no subprocess. mcp
  2.x supports this and it is genuinely faster, but it skips the process
  boundary — so it is for unit tests only, never for a recorded run.
"""

from __future__ import annotations

import sys
from contextlib import AsyncExitStack
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, Self, runtime_checkable

from mcp import Client, StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
from mcp.server.mcpserver import MCPServer

from analyst.contracts import Contract


class ToolCallResult(Contract):
    """A tool call's outcome, in a form that survives a cassette round-trip.

    `structured` is the tool's structured output (mcp 2.x `structured_content`).
    Keeping the typed dict rather than the rendered text block is what lets the
    SQL Analyst read `ref_id` and `row_count` without parsing prose.
    """

    tool: str
    ok: bool
    structured: dict[str, Any] | None = None
    text: str | None = None
    error: str | None = None


@runtime_checkable
class MCPClient(Protocol):
    """The seam. Both the live clients and the replay interceptor satisfy it."""

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolCallResult: ...


def _to_result(name: str, raw: Any) -> ToolCallResult:
    """Normalise an mcp CallToolResult into our contract."""
    is_error = bool(getattr(raw, "is_error", False))
    structured = getattr(raw, "structured_content", None)
    text: str | None = None
    for block in getattr(raw, "content", None) or []:
        if getattr(block, "type", None) == "text":
            text = block.text
            break
    return ToolCallResult(
        tool=name,
        ok=not is_error,
        structured=structured if isinstance(structured, dict) else None,
        text=text,
        error=text if is_error else None,
    )


class StdioMCPClient:
    """Speaks MCP to a subprocess over stdio (the §4 transport)."""

    def __init__(self, warehouse: Path, results_dir: Path) -> None:
        self._params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "analyst.mcp.server",
                "--warehouse",
                str(warehouse),
                "--results-dir",
                str(results_dir),
            ],
        )
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def __aenter__(self) -> Self:
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self._session = await self._stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._session = None
        await self._stack.aclose()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        if self._session is None:
            raise RuntimeError("StdioMCPClient used outside its async context")
        raw = await self._session.call_tool(name, arguments)
        return _to_result(name, raw)


class InProcessMCPClient:
    """Binds a server object directly. Unit tests only — no process boundary."""

    def __init__(self, server: MCPServer) -> None:
        self._server = server
        self._client: Client | None = None
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        self._client = await self._stack.enter_async_context(Client(self._server))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._client = None
        await self._stack.aclose()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        if self._client is None:
            raise RuntimeError("InProcessMCPClient used outside its async context")
        raw = await self._client.call_tool(name, arguments)
        return _to_result(name, raw)
