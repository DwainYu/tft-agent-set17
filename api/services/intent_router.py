"""Intent router – decide what the user is asking and extract entities."""
from __future__ import annotations

import sqlite3
from typing import Literal

from api.services.entity_matcher import EntityMatcher

Direction = Literal["推荐阵容", "推荐装备", "查专属", "检索装备"]

# Direction -> tool name mapping (must match ToolDispatcher)
_DIRECTION_TOOL: dict[str, str] = {
    "推荐阵容": "query_comps",
    "推荐装备": "query_items",
    "查专属": "query_specific",
    "检索装备": "search_items",
}


class IntentRouter:
    """Route a user question to an intent and extract entities."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._matcher = EntityMatcher(conn)

    def route(self, question: str, direction: str | None = None) -> tuple[str, list[dict]]:
        """Return ``(tool_name, entities)`` for *question*.

        If *direction* is given by the caller it maps directly to a tool.
        Otherwise a heuristic based on extracted entities is used.
        """
        entities = self._matcher.match(question)

        if direction and direction in _DIRECTION_TOOL:
            tool = _DIRECTION_TOOL[direction]
        else:
            tool = self._infer_tool(entities)

        return tool, entities

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_tool(entities: list[dict]) -> str:
        """Heuristic: champion+item → query_specific; champion → query_comps; item → query_items."""
        has_champ = any(e["type"] == "champion" for e in entities)
        has_item = any(e["type"] == "item" for e in entities)

        if has_champ and has_item:
            return "query_specific"
        if has_champ:
            return "query_comps"
        if has_item:
            return "query_items"
        return "query_comps"  # default
