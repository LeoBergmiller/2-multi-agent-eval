"""Two-seam cassette layer: LLM client and MCP client (architecture.md \u00a76.2)."""

from analyst.replay.llm_seam import ReplayingLLMClient, build_llm_client
from analyst.replay.mcp_seam import ReplayingMCPClient
from analyst.replay.store import (
    CassetteMissError,
    CassetteMode,
    CassetteStore,
    canonical_key,
    cassettes_root,
)

__all__ = [
    "CassetteMissError",
    "CassetteMode",
    "CassetteStore",
    "ReplayingLLMClient",
    "ReplayingMCPClient",
    "build_llm_client",
    "canonical_key",
    "cassettes_root",
]
