"""Chat router — SSE streaming powered by the LangGraph agent.

SSE stage mapping (backward-compatible with the existing frontend)::

    LangGraph node   →  SSE stage
    ─────────────────────────────────
    (entity match)   →  understanding
    planner          →  tool_selection
    executor         →  tool_execution → tool_done
    critic (retry)   →  (loops back, no extra SSE)
    reflect          →  composing → result

Human-in-loop:
    POST /ask          – normal flow (no interrupt)
    POST /ask/plan     – run planner only, return plan for inspection
    POST /ask/resume   – resume an interrupted graph (after plan approval)

LangSmith tracing:
    Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY in .env to enable.
    Traces appear under project "tft-agent-set17" (configurable via LANGCHAIN_PROJECT).
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from api.agent.graph import get_agent_app, get_agent_app_with_interrupt
from api.agent.state import AgentState
from api.config import get_settings
from api.core.sse import SSEEvent
from api.models.chat import AskRequest
from api.services.entity_matcher import EntityMatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ask", tags=["chat"])

# Tool name → friendly Chinese display name for SSE messages
_TOOL_DISPLAY: dict[str, str] = {
    "query_comps": "阵容推荐",
    "query_items": "装备查询",
    "query_specific": "专属查询",
    "search_items": "装备搜索",
    "rag_search": "语义检索",
    "graph_query": "图谱查询",
    "get_champion_info": "英雄信息",
    "get_trait_info": "羁绊信息",
    "get_item_info": "装备信息",
    "calc_synergy": "协同计算",
    "get_version_meta": "版本概览",
}


def _open_db() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _match_entities(question: str) -> list[dict]:
    """Run entity matching against the question text."""
    conn = _open_db()
    try:
        matcher = EntityMatcher(conn)
        return matcher.match(question)
    finally:
        conn.close()


def _initial_state(req: AskRequest, entities: list[dict]) -> dict[str, Any]:
    """Build the initial AgentState from the request."""
    return {
        "messages": [HumanMessage(content=req.question)],
        "question": req.question,
        "direction": req.direction,
        "entities": entities,
        "plan": [],
        "tool_results": [],
        "critique": "",
        "should_retry": False,
        "iteration": 0,
        "final_answer": "",
        "card_data": None,
        "error": None,
    }


def _thread_id(req: AskRequest) -> str:
    """Derive a stable thread ID for checkpoint persistence."""
    return req.conversation_id or str(uuid.uuid4())


# ---------------------------------------------------------------------------
# POST /ask — main SSE streaming endpoint (agent-powered)
# ---------------------------------------------------------------------------

@router.post("")
async def ask_question(req: AskRequest):
    """Main chat endpoint — streams LangGraph agent execution as SSE."""

    async def event_generator():
        # Stage 1: Entity matching → "understanding"
        entities = _match_entities(req.question)
        entity_names = (
            ", ".join(e.get("name_zh", e.get("canonical_id", "")) for e in entities)
            if entities
            else req.question
        )
        yield SSEEvent(
            stage="understanding",
            content=f"用户问的是{entity_names}，方向是{req.direction or '自动识别'}",
        ).encode()
        await asyncio.sleep(0.05)

        # Build initial state and config
        state = _initial_state(req, entities)
        config = {
            "configurable": {"thread_id": _thread_id(req)},
            "metadata": {"question": req.question, "direction": req.direction},
        }

        app = await get_agent_app()

        try:
            # Stream LangGraph node updates as SSE events
            async for event in app.astream(state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    sse_events = _map_node_to_sse(node_name, node_output)
                    for sse in sse_events:
                        yield sse.encode()
                        await asyncio.sleep(0.05)

        except Exception as exc:
            logger.exception("Agent graph execution failed")
            yield SSEEvent(
                stage="result",
                data={"card": None, "summary": f"Agent 执行出错: {exc}", "results": []},
            ).encode()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /ask/plan — run planner only, return plan for human inspection
# ---------------------------------------------------------------------------

@router.post("/plan")
async def ask_plan(req: AskRequest):
    """Run only the planner node and return the tool-call plan.

    This enables human-in-loop: the user can inspect the plan before
    approving execution via /ask/resume.
    """
    entities = _match_entities(req.question)
    state = _initial_state(req, entities)
    config = {
        "configurable": {"thread_id": _thread_id(req)},
    }

    app = await get_agent_app_with_interrupt()

    try:
        # Run until interrupt_before=["executor"] pauses the graph
        result = None
        async for event in app.astream(state, config=config, stream_mode="updates"):
            result = event

        # Extract the plan from the last planner output
        plan = []
        if result and "planner" in result:
            plan = result["planner"].get("plan", [])

        return {
            "thread_id": config["configurable"]["thread_id"],
            "plan": plan,
            "entities": entities,
            "status": "awaiting_approval",
        }
    except Exception as exc:
        logger.exception("Plan generation failed")
        return {"error": str(exc), "status": "error"}


# ---------------------------------------------------------------------------
# POST /ask/resume — resume an interrupted graph after plan approval
# ---------------------------------------------------------------------------

@router.post("/resume")
async def ask_resume(thread_id: str):
    """Resume an interrupted agent graph (after human-in-loop plan approval).

    The graph was paused before the executor node.  Calling this endpoint
    continues execution from the checkpoint.
    """

    async def event_generator():
        config = {"configurable": {"thread_id": thread_id}}
        app = await get_agent_app_with_interrupt()

        try:
            # Resume with None input to continue from checkpoint
            async for event in app.astream(None, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    sse_events = _map_node_to_sse(node_name, node_output)
                    for sse in sse_events:
                        yield sse.encode()
                        await asyncio.sleep(0.05)
        except Exception as exc:
            logger.exception("Agent resume failed")
            yield SSEEvent(
                stage="result",
                data={"card": None, "summary": f"恢复执行出错: {exc}", "results": []},
            ).encode()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# SSE mapping helpers
# ---------------------------------------------------------------------------

def _map_node_to_sse(node_name: str, output: dict[str, Any]) -> list[SSEEvent]:
    """Map a LangGraph node update to SSE events (backward-compatible stages)."""
    events: list[SSEEvent] = []

    if node_name == "planner":
        plan = output.get("plan", [])
        tool_names = [
            _TOOL_DISPLAY.get(p.get("tool", ""), p.get("tool", ""))
            for p in plan
        ]
        tools_str = "、".join(tool_names) if tool_names else "数据查询"
        events.append(SSEEvent(
            stage="tool_selection",
            content=f"TFT-Agent 决定使用 {tools_str} 工具查询数据",
        ))

    elif node_name == "executor":
        results = output.get("tool_results", [])
        events.append(SSEEvent(
            stage="tool_execution",
            content="TFT-Agent 正在查询数据库...",
        ))
        success_count = sum(1 for r in results if r.get("success"))
        total_items = 0
        for r in results:
            data = r.get("data")
            if isinstance(data, list):
                total_items += len(data)
            elif isinstance(data, dict):
                total_items += 1
        events.append(SSEEvent(
            stage="tool_done",
            content=f"TFT-Agent 查完了，{success_count}/{len(results)} 个工具成功，共 {total_items} 条数据",
        ))

    elif node_name == "critic":
        critique = output.get("critique", "")
        should_retry = output.get("should_retry", False)
        if should_retry:
            events.append(SSEEvent(
                stage="tool_execution",
                content=f"TFT-Agent 认为结果不够充分（{critique[:60]}），正在重新规划...",
            ))

    elif node_name == "reflect":
        answer = output.get("final_answer", "")
        card_data = output.get("card_data")
        # Collect all tool results for the frontend
        events.append(SSEEvent(stage="composing", content=answer[:200]))
        events.append(SSEEvent(
            stage="result",
            data={
                "card": card_data,
                "summary": answer,
                "results": [],  # individual results available via tool_results in state
            },
        ))

    return events


# ---------------------------------------------------------------------------
# Health check (unchanged)
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok", "service": "chat", "agent": "langgraph"}
