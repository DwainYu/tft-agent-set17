"""Query best items from the item_stats table."""
from __future__ import annotations

import sqlite3

MIN_SAMPLE = 20  # minimum sample_size for reliable stats


class ItemQuery:
    """Retrieve item performance data with confidence thresholds."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def query(self, champion_id: str | None = None) -> list[dict]:
        """Return items ranked by delta_rank (lower = better).

        If *champion_id* is given, only stats for that champion are returned.
        Otherwise global stats (all champions aggregated) are used.
        EmptyBag and low-sample items are filtered out.
        """
        if champion_id:
            sql = (
                "SELECT ist.item_id, i.name_zh, i.name_en, "
                "       ist.delta_rank, ist.sample_size "
                "FROM item_stats ist "
                "JOIN items i ON i.id = ist.item_id "
                "WHERE ist.champion_id = ? "
                "  AND ist.item_id NOT IN ('TFT_Item_EmptyBag') "
                "  AND i.name_zh != '' "
                "  AND ist.sample_size >= ? "
                "ORDER BY ist.delta_rank ASC "
                "LIMIT 20"
            )
            params: tuple = (champion_id, MIN_SAMPLE)
        else:
            sql = (
                "SELECT ist.item_id, i.name_zh, i.name_en, "
                "       ROUND(AVG(ist.delta_rank), 2) AS delta_rank, "
                "       SUM(ist.sample_size) AS sample_size "
                "FROM item_stats ist "
                "JOIN items i ON i.id = ist.item_id "
                "WHERE ist.item_id NOT IN ('TFT_Item_EmptyBag') "
                "  AND i.name_zh != '' "
                "GROUP BY ist.item_id "
                "HAVING SUM(ist.sample_size) >= ? "
                "ORDER BY delta_rank ASC "
                "LIMIT 20"
            )
            params = (MIN_SAMPLE,)

        cur = self._conn.execute(sql, params)
        columns = ["item_id", "name_zh", "name_en", "delta_rank", "sample_size"]
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def query_by_ids(self, item_ids: list[str]) -> list[dict]:
        """Return delta stats for specific item IDs."""
        if not item_ids:
            return []
        placeholders = ",".join("?" * len(item_ids))
        sql = (
            f"SELECT ist.item_id, i.name_zh, i.name_en, "
            f"       ist.champion_id, ist.delta_rank, ist.sample_size "
            f"FROM item_stats ist "
            f"JOIN items i ON i.id = ist.item_id "
            f"WHERE ist.item_id IN ({placeholders}) "
            f"  AND ist.item_id NOT IN ('TFT_Item_EmptyBag') "
            f"  AND ist.sample_size >= ? "
            f"ORDER BY ist.delta_rank ASC"
        )
        cur = self._conn.execute(sql, (*item_ids, MIN_SAMPLE))
        columns = ["item_id", "name_zh", "name_en", "champion_id", "delta_rank", "sample_size"]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def search(self, keywords: list[str]) -> list[dict]:
        """Fuzzy search items by name, return basic info + best delta."""
        if not keywords:
            return []
        like_clauses = " OR ".join(["i.name_zh LIKE ?"] * len(keywords))
        params = [f"%{k}%" for k in keywords]
        sql = (
            f"SELECT i.id AS item_id, i.name_zh, i.name_en, "
            f"       MIN(s.delta_rank) AS delta_rank, "
            f"       MAX(s.sample_size) AS sample_size "
            f"FROM items i "
            f"LEFT JOIN item_stats s ON i.id = s.item_id "
            f"  AND s.sample_size >= {MIN_SAMPLE} "
            f"  AND s.item_id NOT IN ('TFT_Item_EmptyBag') "
            f"WHERE ({like_clauses}) AND i.name_zh != '' "
            f"GROUP BY i.id "
            f"ORDER BY delta_rank ASC NULLS LAST "
            f"LIMIT 20"
        )
        cur = self._conn.execute(sql, params)
        columns = ["item_id", "name_zh", "name_en", "delta_rank", "sample_size"]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
