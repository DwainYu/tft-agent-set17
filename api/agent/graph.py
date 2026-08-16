"""LangGraph StateGraph assembly — wires Planner→Executor→Critic→Reflect.

Graph topology::

    START ──→ planner ──→ executor ──→ critic ──→ reflect ──→ END
                              ↑           |
                              └── retry ──┘  (conditional, ≤ AGENT_MAX_ITERATIONS)

Checkpoint: AsyncSqliteSaver for dev (data/checkpoints.db).
Human-in-loop: ``interrupt_before=["executor"]`` pauses the graph before
tool execution so the caller can inspect / modify the plan.
"""
from __future__ import annotations

import logging
from typing import Any

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from api.agent.nodes import (
    critic_node,
    executor_node,
    planner_node,
    reflect_node,
    should_retry,
)
from api.agent.state import AgentState
from api.config import get_settings

logger = logging.getLogger(__name__)


def build_agent_graph(
    *,
    interrupt_before_executor: bool = False,
) -> StateGraph:
    """Construct the agent StateGraph (uncompiled).

    Parameters
    ----------
    interrupt_before_executor:
        When True the graph pauses before the executor node, enabling
        human-in-loop plan inspection / modification.
    """
    graph = StateGraph(AgentState)

    # ── Nodes ──────────────────────────────────────────────────
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("critic", critic_node)
    graph.add_node("reflect", reflect_node)

    # ── Edges ──────────────────────────────────────────────────
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "critic")

    # Critic → retry (back to planner) or done (to reflect)
    graph.add_conditional_edges(
        "critic",
        should_retry,
        {"retry": "planner", "done": "reflect"},
    )
    graph.add_edge("reflect", END)

    return graph


def compile_agent(
    *,
    checkpointer: Any | None = None,
    interrupt_before_executor: bool = False,
) -> Any:
    """Compile the graph with an optional checkpointer.

    Returns a runnable LangGraph ``CompiledGraph``.
    """
    graph = build_agent_graph(interrupt_before_executor=interrupt_before_executor)

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if interrupt_before_executor:
        compile_kwargs["interrupt_before"] = ["executor"]

    compiled = graph.compile(**compile_kwargs)
    logger.info(
        "Agent graph compiled (checkpointer=%s, interrupt=%s)",
        type(checkpointer).__name__ if checkpointer else "None",
        interrupt_before_executor,
    )
    return compiled


# ---------------------------------------------------------------------------
# Singleton app with async SQLite checkpointer
# ---------------------------------------------------------------------------

_agent_app: Any = None
_agent_app_interrupt: Any = None
# Keep references to the underlying aiosqlite connections so they can be
# closed explicitly.  aiosqlite spawns a *non-daemon* worker thread per
# connection; if the connections are never closed the interpreter hangs at
# shutdown (threading._shutdown waits for those threads forever).
_checkpointer_conns: list[Any] = []


async def close_agent_apps() -> None:
    """Close checkpoint connections and reset the compiled-app singletons.

    Call this on FastAPI lifespan shutdown and in test teardown so the
    aiosqlite worker threads can exit and the process can terminate.
    """
    global _agent_app, _agent_app_interrupt

    for conn in _checkpointer_conns:
        try:
            await conn.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to close checkpoint connection: %s", exc)
    _checkpointer_conns.clear()
    _agent_app = None
    _agent_app_interrupt = None


async def get_agent_app() -> Any:
    """Return a compiled agent graph with async SQLite checkpoint persistence.

    The checkpointer enables:
    - Conversation state persistence across requests
    - Human-in-loop resume (interrupt → inspect → continue)
    - Crash recovery (reload from last checkpoint)
    """
    global _agent_app
    if _agent_app is None:
        settings = get_settings()
        conn = await aiosqlite.connect(settings.CHECKPOINT_DB)
        _checkpointer_conns.append(conn)
        checkpointer = AsyncSqliteSaver(conn)
        _agent_app = compile_agent(
            checkpointer=checkpointer, interrupt_before_executor=False
        )
    return _agent_app


async def get_agent_app_with_interrupt() -> Any:
    """Return a compiled agent graph with human-in-loop interrupt enabled.

    Use this variant when the caller wants to pause before tool execution
    and let the user inspect / modify the plan.
    """
    global _agent_app_interrupt
    if _agent_app_interrupt is None:
        settings = get_settings()
        conn = await aiosqlite.connect(settings.CHECKPOINT_DB)
        _checkpointer_conns.append(conn)
        checkpointer = AsyncSqliteSaver(conn)
        _agent_app_interrupt = compile_agent(
            checkpointer=checkpointer, interrupt_before_executor=True
        )
    return _agent_app_interrupt
