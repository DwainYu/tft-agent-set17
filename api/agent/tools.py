"""Tool Registry — 11 tools for the TFT Set 17 Agent.

Each tool is registered with a JSON Schema so the LLM planner can
invoke them via OpenAI function-calling.  Tools that depend on
external services (Milvus, Neo4j) degrade gracefully when those
services are unavailable.

Tools
-----
1.  query_comps      – champion-centric composition lookup
2.  query_items      – best items for a champion
3.  query_specific   – champion-specific item deltas
4.  search_items     – keyword search across all items
5.  rag_search       – BGE-M3 hybrid vector search (Milvus)
6.  graph_query      – Neo4j two-hop synergy traversal
7.  get_champion_info – champion details (cost, traits, icon)
8.  get_trait_info   – trait details (member champions)
9.  get_item_info    – item details (stats, build path)
10. calc_synergy     – trait overlap between two champions
11. get_version_meta – current patch meta summary
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema fragments (reused across tools)
# ---------------------------------------------------------------------------
_CHAMPION_ID = {
    "type": "string",
    "description": "Champion canonical ID, e.g. TFT17_Zed",
}
_ITEM_KEYWORDS = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Item name keywords to search, e.g. ['暴风大剑']",
}


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Central registry that maps tool names → callables + JSON Schema.

    Usage::

        registry = ToolRegistry(conn)
        schemas = registry.openai_schemas()   # for LLM bind_tools
        result  = registry.execute("query_comps", {"champion_ids": ["TFT17_Zed"]})
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._tools: dict[str, dict[str, Any]] = {}
        self._register_all()

    # -- public API ---------------------------------------------------------

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run a tool by name.  Returns ``{"success": bool, "data": ..., "error": ...}``."""
        entry = self._tools.get(name)
        if entry is None:
            return {"success": False, "data": None, "error": f"Unknown tool: {name}"}
        try:
            data = entry["fn"](**args)
            return {"success": True, "data": data, "error": None}
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return {"success": False, "data": None, "error": str(exc)}

    def openai_schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI function-calling compatible tool definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": entry["description"],
                    "parameters": entry["parameters"],
                },
            }
            for name, entry in self._tools.items()
        ]

    def tool_names(self) -> list[str]:
        return list(self._tools)

    # -- registration -------------------------------------------------------

    def _register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        fn: Any,
    ) -> None:
        self._tools[name] = {
            "description": description,
            "parameters": parameters,
            "fn": fn,
        }

    def _register_all(self) -> None:
        conn = self._conn

        # Lazy-import heavy services so the module loads without them
        from api.services.comp_query import CompQuery
        from api.services.item_query import ItemQuery

        comp_q = CompQuery(conn)
        item_q = ItemQuery(conn)

        # 1 ─ query_comps
        self._register(
            "query_comps",
            "查询英雄核心阵容，返回阵容卡片（英雄、羁绊、推荐装备）。",
            {
                "type": "object",
                "properties": {
                    "champion_ids": {
                        "type": "array",
                        "items": _CHAMPION_ID,
                        "description": "英雄 ID 列表",
                    },
                },
                "required": ["champion_ids"],
            },
            lambda champion_ids: comp_q.query(champion_ids),
        )

        # 2 ─ query_items
        self._register(
            "query_items",
            "查询英雄推荐装备（按 delta_rank 排序），或全局热门装备。",
            {
                "type": "object",
                "properties": {
                    "champion_id": {
                        **_CHAMPION_ID,
                        "description": "英雄 ID（可选，不传则返回全局热门）",
                    },
                },
                "required": [],
            },
            lambda champion_id=None: _filter_empty(item_q.query(champion_id)),
        )

        # 3 ─ query_specific
        self._register(
            "query_specific",
            "查询指定英雄的专属装备推荐（delta_rank 排序）。",
            {
                "type": "object",
                "properties": {"champion_id": _CHAMPION_ID},
                "required": ["champion_id"],
            },
            lambda champion_id: _filter_empty(item_q.query(champion_id)),
        )

        # 4 ─ search_items
        self._register(
            "search_items",
            "按关键词搜索装备（模糊匹配中文名）。",
            {
                "type": "object",
                "properties": {"keywords": _ITEM_KEYWORDS},
                "required": ["keywords"],
            },
            lambda keywords: _filter_empty(item_q.search(keywords)),
        )

        # 5 ─ rag_search (Milvus hybrid search, graceful degradation)
        self._register(
            "rag_search",
            "语义向量检索：用 BGE-M3 混合搜索查询 TFT 知识库。",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "自然语言查询"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            self._rag_search,
        )

        # 6 ─ graph_query (Neo4j two-hop, graceful degradation)
        self._register(
            "graph_query",
            "图数据库查询：查找英雄羁绊协同（两跳推理）。",
            {
                "type": "object",
                "properties": {
                    "champion_name": {"type": "string", "description": "英雄中文名"},
                },
                "required": ["champion_name"],
            },
            self._graph_query,
        )

        # 7 ─ get_champion_info
        self._register(
            "get_champion_info",
            "获取英雄详细信息（费用、羁绊、图标路径）。",
            {
                "type": "object",
                "properties": {"champion_id": _CHAMPION_ID},
                "required": ["champion_id"],
            },
            lambda champion_id: self._get_champion_info(champion_id),
        )

        # 8 ─ get_trait_info
        self._register(
            "get_trait_info",
            "获取羁绊详情（成员英雄列表）。",
            {
                "type": "object",
                "properties": {
                    "trait_name": {"type": "string", "description": "羁绊中文名，如 暗星"},
                },
                "required": ["trait_name"],
            },
            lambda trait_name: self._get_trait_info(trait_name),
        )

        # 9 ─ get_item_info
        self._register(
            "get_item_info",
            "获取装备详情（合成路径、属性）。",
            {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "装备中文名"},
                },
                "required": ["item_name"],
            },
            lambda item_name: self._get_item_info(item_name),
        )

        # 10 ─ calc_synergy
        self._register(
            "calc_synergy",
            "计算两个英雄之间的羁绊协同（共享羁绊数量）。",
            {
                "type": "object",
                "properties": {
                    "champion_a": _CHAMPION_ID,
                    "champion_b": _CHAMPION_ID,
                },
                "required": ["champion_a", "champion_b"],
            },
            lambda champion_a, champion_b: self._calc_synergy(champion_a, champion_b),
        )

        # 11 ─ get_version_meta
        self._register(
            "get_version_meta",
            "获取当前版本 meta 概览（各费用英雄数量、羁绊统计）。",
            {
                "type": "object",
                "properties": {},
                "required": [],
            },
            self._get_version_meta,
        )

    # -- tool implementations -----------------------------------------------

    def _rag_search(self, query: str, top_k: int = 5) -> list[dict]:
        try:
            from api.services.rag.engine import RAGEngine
            from api.services.rag.embedding import BGEEmbedding
            from api.services.rag.reranker import BGEReranker

            embedding = BGEEmbedding()
            reranker = BGEReranker()
            engine = RAGEngine(embedding=embedding, reranker=reranker)
            docs, latency = engine.query(query, top_k=top_k)
            return [
                {"content": d.content, "score": d.score, "metadata": d.metadata}
                for d in docs
            ]
        except Exception as exc:
            logger.warning("rag_search unavailable: %s", exc)
            return [{"content": f"RAG 服务暂不可用: {exc}", "score": 0, "metadata": {}}]

    def _graph_query(self, champion_name: str) -> list[dict]:
        try:
            from api.services.rag.graph_store import GraphStore

            store = GraphStore()
            store.connect()
            try:
                return store.get_champion_synergies(champion_name)
            finally:
                store.close()
        except Exception as exc:
            logger.warning("graph_query unavailable: %s", exc)
            return [{"error": f"图数据库暂不可用: {exc}"}]

    def _get_champion_info(self, champion_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id, name_zh, name_en, cost, icon_path FROM champions WHERE id = ?",
            (champion_id,),
        ).fetchone()
        if row is None:
            return None
        traits = [
            r[0]
            for r in self._conn.execute(
                "SELECT t.name_zh FROM champion_traits ct "
                "JOIN traits t ON ct.trait_id = t.id WHERE ct.champion_id = ?",
                (champion_id,),
            ).fetchall()
        ]
        return {
            "id": row[0],
            "name_zh": row[1],
            "name_en": row[2],
            "cost": row[3],
            "icon_path": row[4],
            "traits": traits,
        }

    def _get_trait_info(self, trait_name: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id, name_zh, name_en FROM traits WHERE name_zh = ?",
            (trait_name,),
        ).fetchone()
        if row is None:
            return None
        members = [
            {"id": r[0], "name_zh": r[1], "cost": r[2]}
            for r in self._conn.execute(
                "SELECT c.id, c.name_zh, c.cost FROM champion_traits ct "
                "JOIN champions c ON ct.champion_id = c.id WHERE ct.trait_id = ?",
                (row[0],),
            ).fetchall()
        ]
        return {"id": row[0], "name_zh": row[1], "name_en": row[2], "members": members}

    def _get_item_info(self, item_name: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id, name_zh, name_en, icon_path FROM items WHERE name_zh LIKE ?",
            (f"%{item_name}%",),
        ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "name_zh": row[1], "name_en": row[2], "icon_path": row[3]}

    def _calc_synergy(self, champion_a: str, champion_b: str) -> dict:
        traits_a = {
            r[0]
            for r in self._conn.execute(
                "SELECT trait_id FROM champion_traits WHERE champion_id = ?",
                (champion_a,),
            ).fetchall()
        }
        traits_b = {
            r[0]
            for r in self._conn.execute(
                "SELECT trait_id FROM champion_traits WHERE champion_id = ?",
                (champion_b,),
            ).fetchall()
        }
        shared = traits_a & traits_b
        shared_names = []
        for tid in shared:
            r = self._conn.execute("SELECT name_zh FROM traits WHERE id = ?", (tid,)).fetchone()
            if r:
                shared_names.append(r[0])
        return {
            "champion_a": champion_a,
            "champion_b": champion_b,
            "shared_traits": shared_names,
            "synergy_count": len(shared_names),
        }

    def _get_version_meta(self) -> dict:
        cost_dist = dict(
            self._conn.execute(
                "SELECT cost, COUNT(*) FROM champions GROUP BY cost ORDER BY cost"
            ).fetchall()
        )
        trait_count = self._conn.execute("SELECT COUNT(*) FROM traits").fetchone()[0]
        champ_count = self._conn.execute("SELECT COUNT(*) FROM champions").fetchone()[0]
        return {
            "set": "Set 17 Space Gods",
            "total_champions": champ_count,
            "total_traits": trait_count,
            "cost_distribution": {f"{k}费": v for k, v in cost_dist.items()},
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filter_empty(results: list[dict]) -> list[dict]:
    """Remove EmptyBag placeholder items."""
    return [
        r
        for r in results
        if r.get("item_id", "") not in ("TFT_Item_EmptyBag", "EmptyBag", "")
    ]
