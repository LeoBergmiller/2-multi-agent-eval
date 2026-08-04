"""A REPLAY cassette miss must raise, never fall through to live.

architecture.md §6.2 and §13. This is the load-bearing test for the whole
replay design: if a miss could silently reach the network, CI would stop being
hermetic and would do so invisibly — a green build that made an API call is
worse than a red one.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from analyst.mcp.client import ToolCallResult
from analyst.replay import (
    CassetteMissError,
    CassetteMode,
    CassetteStore,
    ReplayingMCPClient,
)


class RecordingFake:
    """A live client that works perfectly — so any fall-through would succeed
    and go unnoticed. That is exactly what must not happen."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        self.calls.append(name)
        return ToolCallResult(tool=name, ok=True, structured={"n": 37})


ARGS = {"query": "SELECT 1"}
OTHER = {"query": "SELECT 2"}


@pytest.mark.integration
class TestReplayMiss:
    def _record(self, root: Path) -> RecordingFake:
        inner = RecordingFake()
        client = ReplayingMCPClient(inner, CassetteStore(CassetteMode.RECORD, root))
        asyncio.run(client.call_tool("run_sql", ARGS))
        return inner

    def test_hit_is_served_without_a_live_client(self, cassettes_root: Path) -> None:
        self._record(cassettes_root)
        replay = ReplayingMCPClient(
            None, CassetteStore(CassetteMode.REPLAY, cassettes_root)
        )
        result = asyncio.run(replay.call_tool("run_sql", ARGS))
        assert result.structured == {"n": 37}

    def test_miss_raises(self, cassettes_root: Path) -> None:
        self._record(cassettes_root)
        replay = ReplayingMCPClient(
            None, CassetteStore(CassetteMode.REPLAY, cassettes_root)
        )
        with pytest.raises(CassetteMissError):
            asyncio.run(replay.call_tool("run_sql", OTHER))

    def test_miss_raises_even_when_a_working_live_client_is_available(
        self, cassettes_root: Path
    ) -> None:
        """The strong form. A miss must not use a live client that is sitting
        right there and would have answered."""
        self._record(cassettes_root)
        inner = RecordingFake()
        replay = ReplayingMCPClient(
            inner, CassetteStore(CassetteMode.REPLAY, cassettes_root)
        )

        with pytest.raises(CassetteMissError):
            asyncio.run(replay.call_tool("run_sql", OTHER))

        assert inner.calls == [], "REPLAY fell through to the live client"

    def test_miss_message_is_actionable(self, cassettes_root: Path) -> None:
        replay = ReplayingMCPClient(
            None, CassetteStore(CassetteMode.REPLAY, cassettes_root)
        )
        with pytest.raises(CassetteMissError) as excinfo:
            asyncio.run(replay.call_tool("run_sql", ARGS))
        message = str(excinfo.value)
        assert "never falls through" in message
        assert "make demo MODE=record" in message


class TestKeying:
    def test_key_is_order_independent(self, cassettes_root: Path) -> None:
        """Python dict order must not leak into the hash, or a byte-identical
        request would miss."""
        store = CassetteStore(CassetteMode.RECORD, cassettes_root)
        store.save("mcp", {"a": 1, "b": 2}, {"ok": True})
        assert store.load("mcp", {"b": 2, "a": 1}) == {"ok": True}

    def test_different_arguments_are_different_keys(self, cassettes_root: Path) -> None:
        store = CassetteStore(CassetteMode.RECORD, cassettes_root)
        store.save("mcp", {"tool": "run_sql", "arguments": ARGS}, {"ok": True})
        assert store.load("mcp", {"tool": "run_sql", "arguments": OTHER}) is None

    def test_seams_do_not_collide(self, cassettes_root: Path) -> None:
        """Identical payloads on the two seams must not share a cassette."""
        store = CassetteStore(CassetteMode.RECORD, cassettes_root)
        payload = {"same": "payload"}
        store.save("llm", payload, {"seam": "llm"})
        store.save("mcp", payload, {"seam": "mcp"})
        assert store.load("llm", payload) == {"seam": "llm"}
        assert store.load("mcp", payload) == {"seam": "mcp"}

    def test_live_mode_never_reads_cassettes(self, cassettes_root: Path) -> None:
        store = CassetteStore(CassetteMode.RECORD, cassettes_root)
        store.save("mcp", ARGS, {"ok": True})
        live = CassetteStore(CassetteMode.LIVE, cassettes_root)
        assert live.load("mcp", ARGS) is None

    def test_replay_mode_never_writes(self, cassettes_root: Path) -> None:
        store = CassetteStore(CassetteMode.REPLAY, cassettes_root)
        store.save("mcp", ARGS, {"ok": True})
        assert not list((cassettes_root / "mcp").glob("*.json"))
