"""Agent state definition for the LangGraph state machine."""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ToolCallPlan(TypedDict):
    """A single planned tool invocation."""

    tool: str
    args: dict[str, Any]
    reason: str


class AgentState(TypedDict):
    """Full state carried through the Planner→Executor→Critic→Reflect loop.

    Fields
    ------
    messages : conversation history (LangGraph message list, auto-merged)
    question : the user's raw question text
    direction : optional explicit direction hint from the UI
    entities : entities extracted from the question (champion/item/trait/augment)
    plan : list of ToolCallPlan dicts produced by the planner
    tool_results : raw results returned by the executor
    critique : critic's textual assessment of the results
    should_retry : whether the critic wants another planner→executor round
    iteration : current loop counter (guard against infinite loops)
    final_answer : composed natural-language answer
    card_data : structured CompCard dict for the frontend (or None)
    error : error message if something went wrong
    """

    messages: Annotated[list[BaseMessage], add_messages]
    question: str
    direction: str | None
    entities: list[dict[str, Any]]
    plan: list[ToolCallPlan]
    tool_results: list[dict[str, Any]]
    critique: str
    should_retry: bool
    iteration: int
    final_answer: str
    card_data: dict[str, Any] | None
    error: str | None
