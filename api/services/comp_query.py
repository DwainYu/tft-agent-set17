"""Comp (composition) query – build CompCard-shaped results from champion data.

Phase 1: no dedicated ``comps`` table yet. Each card is anchored on one or more
champions; traits and item recommendations are pulled from the DB.
"""
from __future__ import annotations

import sqlite3

MIN_SAMPLE = 20


class CompQuery:
    """Build comp recommendations from the database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def query(self, champion_ids: list[str]) -> list[dict]:
        """Return comp cards anchored on the given champion IDs.

        Each card contains: champion info, traits (synergies), top item
        recommendations with delta values.
        """
        if not champion_ids:
            return []

        results: list[dict] = []
        for champ_id in champion_ids:
            champ = self._get_champion(champ_id)
            if champ is None:
                continue

            traits = self._get_champion_traits(champ_id)
            items = self._get_top_items(champ_id, champ["name_zh"])

            results.append({
                "comp_name": f"{champ['name_zh']} 核心阵容",
                "avg_placement": None,
                "sample_size": None,
                "champions": [champ],
                "synergies": traits,
                "emblems": items[:3],
                "artifacts": items[3:6] if len(items) > 3 else [],
                "flex_slot": None,
            })

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_champion(self, champ_id: str) -> dict | None:
        cur = self._conn.execute(
            "SELECT id, name_zh, name_en, cost, icon_path FROM champions WHERE id = ?",
            (champ_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = ["id", "name_zh", "name_en", "cost", "icon_path"]
        champ = dict(zip(cols, row))
        champ["role"] = None
        # Build icon URL path for frontend
        if champ.get("icon_path"):
            champ["icon"] = f"/assets/{champ['icon_path']}"
        else:
            champ["icon"] = None
        return champ

    def _get_champion_traits(self, champ_id: str) -> list[str]:
        cur = self._conn.execute(
            "SELECT t.name_zh "
            "FROM champion_traits ct "
            "JOIN traits t ON t.id = ct.trait_id "
            "WHERE ct.champion_id = ?",
            (champ_id,),
        )
        return [row[0] for row in cur.fetchall()]

    def _get_top_items(self, champ_id: str, champ_name: str) -> list[dict]:
        cur = self._conn.execute(
            "SELECT i.id AS item_id, i.name_zh, i.name_en, ist.delta_rank "
            "FROM item_stats ist "
            "JOIN items i ON i.id = ist.item_id "
            "WHERE ist.champion_id = ? "
            "  AND ist.item_id NOT IN ('TFT_Item_EmptyBag') "
            "  AND i.name_zh != '' "
            "  AND ist.sample_size >= ? "
            "ORDER BY ist.delta_rank ASC "
            "LIMIT 6",
            (champ_id, MIN_SAMPLE),
        )
        return [
            {
                "item_id": r[0],
                "name_zh": r[1],
                "name_en": r[2],
                "target": champ_name,
                "delta": r[3],
            }
            for r in cur.fetchall()
        ]
