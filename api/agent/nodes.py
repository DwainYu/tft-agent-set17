"""LangGraph nodes — Planner, Executor, Critic, Reflect.

Each node is a pure function ``(state) -> partial_state_update``.
The graph module wires them into a StateGraph with conditional edges.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from api.agent.llm import (
    CRITIC_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    REFLECT_SYSTEM_PROMPT,
    get_llm,
)
from api.agent.state import AgentState, ToolCallPlan
from api.agent.tools import ToolRegistry
from api.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _get_registry(conn: sqlite3.Connection) -> ToolRegistry:
    return ToolRegistry(conn)


def _rule_based_plan(question: str, direction: str | None, entities: list[dict]) -> list[ToolCallPlan]:
    """Fallback planner that mirrors the original IntentRouter logic.

    Enhancements over the original single-tool router:
    - Combines query_comps + query_items when both champion and item keywords appear.
    - Falls back to rag_search for open-ended questions with no matched entities.
    """
    from api.services.intent_router import IntentRouter

    conn = _get_conn()
    try:
        router = IntentRouter(conn)
        tool_name, matched = router.route(question, direction)
    finally:
        conn.close()

    # Use entities from state if available, otherwise from router
    ents = entities or matched
    champion_ids = [e["canonical_id"] for e in ents if e.get("type") == "champion"]
    item_ids = [e["canonical_id"] for e in ents if e.get("type") == "item"]
    item_names = [e["name_zh"] for e in ents if e.get("type") == "item"]
    trait_names = [e["name_zh"] for e in ents if e.get("type") == "trait"]

    plan: list[ToolCallPlan] = []

    # Open-ended question with no entities and no direction → RAG fallback
    if not ents and not direction:
        plan.append({
            "tool": "rag_search",
            "args": {"query": question},
            "reason": "开放性问题，无匹配实体，走语义检索兜底",
        })
        return plan

    if tool_name == "query_comps":
        plan.append({
            "tool": "query_comps",
            "args": {"champion_ids": champion_ids or []},
            "reason": f"用户询问阵容推荐，匹配到英雄: {champion_ids}",
        })
        # If the question also mentions items, add an item query too
        if item_ids or _mentions_items(question):
            plan.append({
                "tool": "query_items",
                "args": {"champion_id": champion_ids[0] if champion_ids else None},
                "reason": "问题同时涉及装备，补充装备查询",
            })
    elif tool_name == "query_items":
        plan.append({
            "tool": "query_items",
            "args": {"champion_id": champion_ids[0] if champion_ids else None},
            "reason": "用户询问装备推荐",
        })
    elif tool_name == "search_items":
        plan.append({
            "tool": "search_items",
            "args": {"keywords": item_names or [question]},
            "reason": "用户搜索装备",
        })
    elif tool_name == "query_specific":
        plan.append({
            "tool": "query_specific",
            "args": {"champion_id": champion_ids[0] if champion_ids else ""},
            "reason": "用户查询英雄专属装备",
        })

    # If a trait was mentioned alongside a champion, add trait info
    if trait_names and champion_ids:
        plan.append({
            "tool": "get_trait_info",
            "args": {"trait_name": trait_names[0]},
            "reason": f"问题涉及羁绊: {trait_names[0]}",
        })

    return plan or [{"tool": "query_comps", "args": {"champion_ids": []}, "reason": "默认阵容查询"}]


_ITEM_KEYWORDS = ("装备", "出装", "出什么", "带什么装", "神器", "纹章", "核心装")


def _mentions_items(question: str) -> bool:
    """Heuristic: does the question reference items/equipment?"""
    return any(kw in question for kw in _ITEM_KEYWORDS)


# ---------------------------------------------------------------------------
# Node: Planner
# ---------------------------------------------------------------------------

def planner_node(state: AgentState) -> dict[str, Any]:
    """Decide which tools to call.

    With LLM: uses OpenAI function-calling to select tools.
    Without LLM: falls back to rule-based IntentRouter logic.
    """
    question = state["question"]
    direction = state.get("direction")
    entities = state.get("entities", [])
    iteration = state.get("iteration", 0)

    logger.info("Planner iteration=%d question=%r direction=%r", iteration, question, direction)

    llm = get_llm()
    if llm is not None:
        return _llm_plan(llm, state, question, direction, entities)

    # Rule-based fallback
    plan = _rule_based_plan(question, direction, entities)
    return {
        "plan": plan,
        "iteration": iteration + 1,
        "messages": [AIMessage(content=f"[Planner] 规划了 {len(plan)} 个工具调用")],
    }


def _llm_plan(
    llm: Any,
    state: AgentState,
    question: str,
    direction: str | None,
    entities: list[dict],
) -> dict[str, Any]:
    """Use LLM tool-calling to produce a plan."""
    conn = _get_conn()
    try:
        registry = _get_registry(conn)
        schemas = registry.openai_schemas()
    finally:
        conn.close()

    tool_desc = "\n".join(
        f"- {s['function']['name']}: {s['function']['description']}"
        for s in schemas
    )
    system_msg = PLANNER_SYSTEM_PROMPT.format(tool_descriptions=tool_desc)

    entity_hint = ""
    if entities:
        names = ", ".join(e.get("name_zh", e.get("canonical_id", "")) for e in entities)
        entity_hint = f"\n识别到的实体: {names}"

    # On retry, feed back the critique and previous results so the planner
    # can adjust its strategy instead of repeating the same plan.
    retry_context = ""
    iteration = state.get("iteration", 0)
    if iteration > 0:
        critique = state.get("critique", "")
        prev_results = state.get("tool_results", [])
        prev_plan = state.get("plan", [])
        if critique or prev_results:
            retry_context = "\n\n【上一轮反馈】\n"
            if prev_plan:
                tried = ", ".join(p.get("tool", "?") for p in prev_plan)
                retry_context += f"已尝试的工具: {tried}\n"
            if critique:
                retry_context += f"评审意见: {critique}\n"
            if prev_results:
                summary = json.dumps(prev_results, ensure_ascii=False, default=str)[:1500]
                retry_context += f"上一轮结果摘要: {summary}\n"
            retry_context += "请根据反馈调整工具计划（换工具、补充查询或调整参数），不要重复完全相同的计划。"

    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=f"用户问题: {question}\n方向提示: {direction or '自动'}{entity_hint}{retry_context}"),
    ]

    try:
        llm_with_tools = llm.bind_tools(schemas)
        response = llm_with_tools.invoke(messages)

        plan: list[ToolCallPlan] = []
        if response.tool_calls:
            for tc in response.tool_calls:
                plan.append({
                    "tool": tc["name"],
                    "args": tc["args"],
                    "reason": f"LLM 选择调用 {tc['name']}",
                })
        else:
            # LLM responded with text instead of tool calls — parse JSON
            plan = _parse_plan_from_text(response.content)

        if not plan:
            plan = _rule_based_plan(question, direction, entities)

        return {
            "plan": plan,
            "iteration": state.get("iteration", 0) + 1,
            "messages": [AIMessage(content=f"[Planner/LLM] 规划了 {len(plan)} 个工具调用")],
        }
    except Exception as exc:
        logger.warning("LLM planning failed: %s — falling back to rules", exc)
        plan = _rule_based_plan(question, direction, entities)
        return {
            "plan": plan,
            "iteration": state.get("iteration", 0) + 1,
            "messages": [AIMessage(content=f"[Planner/Fallback] LLM 不可用，规则规划 {len(plan)} 个工具")],
        }


def _parse_plan_from_text(text: str) -> list[ToolCallPlan]:
    """Try to extract a JSON plan array from LLM text output."""
    try:
        # Find JSON array in the response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(text[start:end])
            return [
                {"tool": it["tool"], "args": it.get("args", {}), "reason": it.get("reason", "")}
                for it in items
                if "tool" in it
            ]
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return []


# ---------------------------------------------------------------------------
# Node: Executor
# ---------------------------------------------------------------------------

def executor_node(state: AgentState) -> dict[str, Any]:
    """Execute all planned tools and collect results."""
    plan = state.get("plan", [])
    if not plan:
        return {
            "tool_results": [],
            "messages": [AIMessage(content="[Executor] 无工具调用计划")],
        }

    conn = _get_conn()
    try:
        registry = _get_registry(conn)
        results: list[dict[str, Any]] = []
        for step in plan:
            tool_name = step["tool"]
            tool_args = step.get("args", {})
            logger.info("Executing tool=%s args=%s", tool_name, tool_args)
            result = registry.execute(tool_name, tool_args)
            result["tool"] = tool_name
            result["reason"] = step.get("reason", "")
            results.append(result)
    finally:
        conn.close()

    success_count = sum(1 for r in results if r.get("success"))
    return {
        "tool_results": results,
        "messages": [
            AIMessage(content=f"[Executor] 执行了 {len(results)} 个工具，{success_count} 个成功")
        ],
    }


# ---------------------------------------------------------------------------
# Node: Critic
# ---------------------------------------------------------------------------

def critic_node(state: AgentState) -> dict[str, Any]:
    """Evaluate tool results and decide whether to retry.

    With LLM: asks the model to assess result quality.
    Without LLM: heuristic — retry if all results are empty/failed.
    """
    results = state.get("tool_results", [])
    iteration = state.get("iteration", 0)
    max_iter = get_settings().AGENT_MAX_ITERATIONS

    # Guard: never exceed max iterations
    if iteration >= max_iter:
        return {
            "critique": f"已达到最大迭代次数 ({max_iter})，停止重试",
            "should_retry": False,
            "messages": [AIMessage(content="[Critic] 达到最大迭代，终止循环")],
        }

    llm = get_llm()
    if llm is not None:
        return _llm_critique(llm, state, results)

    # Rule-based critique
    has_data = any(
        r.get("success") and r.get("data")
        for r in results
    )
    if has_data:
        return {
            "critique": "工具返回了有效数据",
            "should_retry": False,
            "messages": [AIMessage(content="[Critic] 结果有效，无需重试")],
        }

    return {
        "critique": "所有工具返回为空或失败，建议重试",
        "should_retry": True,
        "messages": [AIMessage(content="[Critic] 结果为空，建议重试")],
    }


def _llm_critique(llm: Any, state: AgentState, results: list[dict]) -> dict[str, Any]:
    """Use LLM to assess result quality."""
    results_text = json.dumps(results, ensure_ascii=False, default=str)[:3000]
    messages = [
        SystemMessage(content=CRITIC_SYSTEM_PROMPT),
        HumanMessage(content=f"用户问题: {state['question']}\n\n工具结果:\n{results_text}"),
    ]
    try:
        response = llm.invoke(messages)
        text = response.content.strip()
        should_retry = text.upper().startswith("RETRY")
        return {
            "critique": text,
            "should_retry": should_retry,
            "messages": [AIMessage(content=f"[Critic/LLM] {text[:200]}")],
        }
    except Exception as exc:
        logger.warning("LLM critique failed: %s", exc)
        has_data = any(r.get("success") and r.get("data") for r in results)
        return {
            "critique": f"LLM 评估失败: {exc}",
            "should_retry": not has_data,
            "messages": [AIMessage(content="[Critic/Fallback] LLM 不可用，启发式评估")],
        }


# ---------------------------------------------------------------------------
# Node: Reflect
# ---------------------------------------------------------------------------

def reflect_node(state: AgentState) -> dict[str, Any]:
    """Compose the final answer from tool results.

    With LLM: generates a natural-language response.
    Without LLM: uses template strings (preserving the original SSE contract).
    """
    results = state.get("tool_results", [])
    question = state.get("question", "")

    # Extract card data from query_comps results
    card_data = None
    for r in results:
        if r.get("tool") == "query_comps" and r.get("success") and r.get("data"):
            data = r["data"]
            if isinstance(data, list) and data:
                card_data = data[0]
            elif isinstance(data, dict):
                card_data = data
            break

    llm = get_llm()
    if llm is not None:
        answer = _llm_reflect(llm, state, results)
    else:
        answer = _template_reflect(question, results, card_data)

    return {
        "final_answer": answer,
        "card_data": card_data,
        "messages": [AIMessage(content=f"[Reflect] {answer[:200]}")],
    }


def _llm_reflect(llm: Any, state: AgentState, results: list[dict]) -> str:
    """Generate a natural-language answer via LLM."""
    results_text = json.dumps(results, ensure_ascii=False, default=str)[:4000]
    messages = [
        SystemMessage(content=REFLECT_SYSTEM_PROMPT),
        HumanMessage(content=f"用户问题: {state['question']}\n\n工具查询结果:\n{results_text}"),
    ]
    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as exc:
        logger.warning("LLM reflect failed: %s", exc)
        return _template_reflect(state["question"], results, None)


def _template_reflect(question: str, results: list[dict], card_data: dict | None) -> str:
    """Template-based answer (preserves original behaviour without LLM)."""
    success_results = [r for r in results if r.get("success") and r.get("data")]
    if not success_results:
        return "没有找到相关结果，试试其他关键词？"

    parts: list[str] = []
    for r in success_results:
        tool = r.get("tool", "")
        data = r.get("data")
        if tool == "query_comps" and isinstance(data, list):
            parts.append(f"找到 {len(data)} 个阵容推荐")
        elif tool in ("query_items", "query_specific") and isinstance(data, list):
            parts.append(f"找到 {len(data)} 件推荐装备")
        elif tool == "search_items" and isinstance(data, list):
            parts.append(f"搜索到 {len(data)} 件装备")
        elif tool == "get_champion_info" and isinstance(data, dict):
            parts.append(f"英雄 {data.get('name_zh', '')}：{data.get('cost', '')}费，羁绊 {', '.join(data.get('traits', []))}")
        elif tool == "get_trait_info" and isinstance(data, dict):
            members = data.get("members", [])
            parts.append(f"羁绊 {data.get('name_zh', '')} 共有 {len(members)} 个英雄")
        elif tool == "calc_synergy" and isinstance(data, dict):
            parts.append(f"协同羁绊: {', '.join(data.get('shared_traits', [])) or '无'}")
        elif tool == "get_version_meta" and isinstance(data, dict):
            parts.append(f"当前版本: {data.get('set', '')}，共 {data.get('total_champions', 0)} 个英雄")
        else:
            parts.append(f"{tool} 返回了数据")

    return "；".join(parts) + "。"


# ---------------------------------------------------------------------------
# Conditional edge: should the critic loop back to the planner?
# ---------------------------------------------------------------------------

def should_retry(state: AgentState) -> str:
    """Routing function for the critic → planner/reflect conditional edge."""
    if state.get("should_retry", False):
        return "retry"
    return "done"
