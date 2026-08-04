"""MCP server exposing `run_sql` over stdio.

architecture.md §4 specifies stdio for local dev and CI — hermetic, fast, no
ports. §1/§1.5 name the library "FastMCP"; in mcp 2.x that class is
`MCPServer` (`mcp.server.mcpserver`). The decorator shape §4 shows is
unchanged, so the tool signature is as specified. See D22.

Gate 0 registers one tool. The resources and prompts in §4 (`schema://warehouse`,
`docs://metrics/{doc_id}`, `analyst/plan`, `analyst/sql_style`) land at Gate 1
alongside the other four tools — absent here rather than stubbed.

Run standalone:
    python -m analyst.mcp.server --warehouse data/warehouse.duckdb \\
        --results-dir runs/<run_id>/results
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from analyst.artifacts import ResultStore
from analyst.mcp.tools.sql import QueryResult, SqlRunner

SERVER_NAME = "analyst-warehouse"


def build_server(warehouse: Path, results_dir: Path) -> MCPServer:
    """Construct the server. Separated from `main` so tests can bind in-process."""
    server = MCPServer(
        name=SERVER_NAME,
        instructions=(
            "Read-only access to a healthcare operations warehouse. "
            "SELECT queries only; results are returned as references, not frames."
        ),
    )
    runner = SqlRunner(warehouse, ResultStore(results_dir))

    @server.tool(name="run_sql")
    def run_sql(query: str, max_rows: int = 1000) -> QueryResult:
        """Run a read-only SELECT against the warehouse.

        Returns a reference to the result (schema, row count, and the first five
        rows) — never the full result set. Only the allow-listed tables
        patients, encounters and organizations may be queried.

        Args:
            query: A single SELECT (optionally with CTEs). No DDL, DML, COPY,
                ATTACH, PRAGMA, INSTALL or LOAD.
            max_rows: Row cap; a LIMIT is applied whether or not you supply one.
        """
        return runner.run(query, max_rows=max_rows)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyst MCP server (stdio)")
    parser.add_argument("--warehouse", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    args = parser.parse_args()

    server = build_server(args.warehouse, args.results_dir)
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
