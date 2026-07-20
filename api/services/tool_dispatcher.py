"""Tool dispatcher – routes intents to the appropriate query service."""
from __future__ import annotations

import sqlite3

from api.services.comp_query import CompQuery
from api.services.item_query import ItemQuery


class ToolDispatcher:
    """Given a tool name and extracted entities, call the right query."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._comp_query = CompQuery(conn)
        self._item_query = ItemQuery(conn)

    def dispatch(self, tool: str, entities: list[dict]) -> list[dict]:
        """Dispatch to the appropriate query based on *tool*.

        *entities* is the list produced by :class:`EntityMatcher`, each item
        having at least ``type`` and ``canonical_id`` keys.
        """
        champion_ids = [e["canonical_id"] for e in entities if e.get("type") == "champion"]
        item_ids = [e["canonical_id"] for e in entities if e.get("type") == "item"]

        if tool == "query_comps":
            return self._comp_query.query(champion_ids)

        if tool == "query_items":
            # If specific items mentioned, query those; otherwise per-champion or global
            if item_ids:
                return self._filter_empty(self._item_query.query_by_ids(item_ids))
            champ_id = champion_ids[0] if champion_ids else None
            return self._filter_empty(self._item_query.query(champ_id))

        if tool == "search_items":
            # Fuzzy search by item name keywords
            keywords = [e["name_zh"] for e in entities if e.get("type") == "item"]
            if keywords:
                return self._filter_empty(self._item_query.search(keywords))
            return self._filter_empty(self._item_query.query(None))

        if tool == "query_specific":
            # Champion + item combination
            if champion_ids:
                return self._filter_empty(self._item_query.query(champion_ids[0]))
            return []

        return []

    @staticmethod
    def _filter_empty(results: list[dict]) -> list[dict]:
        """Remove EmptyBag and entries with empty item_id."""
        return [
            r for r in results
            if r.get("item_id", "") not in ("TFT_Item_EmptyBag", "EmptyBag", "")
        ]
