"""LangGraph assembly and checkpointer (architecture.md §3.1, §11).

The checkpointer is **durable execution, not memory** (D9) — keep that
distinction sharp. It lets a run resume; it does not let the agent remember
anything across tasks.
"""

from __future__ import annotations

from functools import partial

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from analyst.graph.nodes.planner import planner_node
from analyst.graph.nodes.sql_analyst import sql_analyst_node
from analyst.graph.nodes.synthesizer import synthesizer_node
from analyst.graph.router import GATE0_SEQUENCE, NodeName, route_after
from analyst.graph.state import AnalystState, RunContext

NODE_FUNCS = {
    "planner": planner_node,
    "sql_analyst": sql_analyst_node,
    "synthesizer": synthesizer_node,
}


def _edge_target(current: NodeName, state: AnalystState) -> str:
    target = route_after(current, state)
    return END if target == "__end__" else target


def build_graph(ctx: RunContext) -> CompiledStateGraph[AnalystState]:
    """Compile the Gate 0 graph.

    `RunContext` is bound into each node with `partial` rather than carried in
    state: clients and file handles are not serialisable, and putting them in
    state would break the checkpointer.
    """
    graph = StateGraph(AnalystState)

    for name, func in NODE_FUNCS.items():
        graph.add_node(name, partial(func, ctx=ctx))

    graph.set_entry_point(GATE0_SEQUENCE[0])
    for name in GATE0_SEQUENCE:
        graph.add_conditional_edges(name, partial(_edge_target, name))

    return graph.compile(checkpointer=InMemorySaver())
