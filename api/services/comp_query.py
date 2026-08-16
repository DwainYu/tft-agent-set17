"""Comp (composition) query – build CompCard-shaped results from mined comp data.

Phase 2: uses the ``comps`` + ``comp_champions`` tables populated by
``scripts/mine_comps.py``.  Falls back to the legacy single-anchor card
when no mined comp matches.
"""
from __future__ import annotations

import json
import sqlite3

MIN_SAMPLE = 20


class CompQuery:
    """Build comp recommendations from the database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(self, champion_ids: list[str]) -> list[dict]:
        """Return comp cards for the given champion IDs.

        Priority:
        1. Comps where the champion is the **anchor** (sorted by sample_size).
        2. Comps where the champion is a **member** (sorted by pick_rate).
        3. Legacy single-anchor fallback if no mined comp matches.
        """
        if not champion_ids:
            return []

        results: list[dict] = []
        for champ_id in champion_ids:
            # 1) Anchor comps
            cards = self._query_by_anchor(champ_id)
            if cards:
                results.extend(cards)
                continue

            # 2) Member comps
            cards = self._query_by_membership(champ_id)
            if cards:
                results.extend(cards)
                continue

            # 3) Legacy fallback
            card = self._legacy_card(champ_id)
            if card:
                results.append(card)

        return results

    # ------------------------------------------------------------------
    # Mined comp queries
    # ------------------------------------------------------------------

    def _query_by_anchor(self, champ_id: str) -> list[dict]:
        """Return all comps anchored on *champ_id*, best first."""
        rows = self._conn.execute(
            "SELECT id FROM comps WHERE anchor_id = ? ORDER BY sample_size DESC LIMIT 3",
            (champ_id,),
        ).fetchall()
        return [self._build_card(r[0]) for r in rows]

    def _query_by_membership(self, champ_id: str) -> list[dict]:
        """Return comps that include *champ_id* as a member, best first."""
        rows = self._conn.execute(
            "SELECT cc.comp_id FROM comp_champions cc "
            "JOIN comps c ON c.id = cc.comp_id "
            "WHERE cc.champion_id = ? "
            "ORDER BY cc.pick_rate DESC, c.sample_size DESC "
            "LIMIT 2",
            (champ_id,),
        ).fetchall()
        return [self._build_card(r[0]) for r in rows]

    def _build_card(self, comp_id: int) -> dict:
        """Assemble a full CompCard dict from a comp row."""
        comp = self._conn.execute(
            "SELECT name, anchor_id, avg_placement, sample_size, top_traits "
            "FROM comps WHERE id = ?",
            (comp_id,),
        ).fetchone()
        if comp is None:
            return {}

        name, anchor_id, avg_placement, sample_size, top_traits_json = comp
        synergies: list[str] = json.loads(top_traits_json) if top_traits_json else []

        # Champions
        champ_rows = self._conn.execute(
            "SELECT cc.champion_id, c.name_zh, c.name_en, c.cost, c.icon_path, "
            "       cc.role, cc.avg_stars, cc.pick_rate "
            "FROM comp_champions cc "
            "JOIN champions c ON c.id = cc.champion_id "
            "WHERE cc.comp_id = ? "
            "ORDER BY c.cost DESC, cc.pick_rate DESC",
            (comp_id,),
        ).fetchall()

        champions: list[dict] = []
        for r in champ_rows:
            cid, name_zh, name_en, cost, icon_path, role, avg_stars, pick_rate = r
            champ: dict = {
                "id": cid,
                "name_zh": name_zh,
                "name_en": name_en,
                "cost": cost,
                "icon_path": icon_path,
                "role": role,
                "icon": f"/assets/{icon_path}" if icon_path else None,
            }
            champions.append(champ)

        # Item recommendations for the anchor
        anchor_name = next(
            (c["name_zh"] for c in champions if c["id"] == anchor_id), ""
        )
        items = self._get_top_items(anchor_id, anchor_name)

        return {
            "comp_name": name,
            "avg_placement": avg_placement,
            "sample_size": sample_size,
            "champions": champions,
            "synergies": synergies,
            "emblems": items[:3],
            "artifacts": items[3:6] if len(items) > 3 else [],
            "flex_slot": None,
        }

    # ------------------------------------------------------------------
    # Legacy fallback (Phase 1 behaviour)
    # ------------------------------------------------------------------

    def _legacy_card(self, champ_id: str) -> dict | None:
        """Build a single-anchor card when no mined comp exists."""
        champ = self._get_champion(champ_id)
        if champ is None:
            return None

        traits = self._get_champion_traits(champ_id)
        items = self._get_top_items(champ_id, champ["name_zh"])

        return {
            "comp_name": f"{champ['name_zh']} 核心阵容",
            "avg_placement": None,
            "sample_size": None,
            "champions": [champ],
            "synergies": traits,
            "emblems": items[:3],
            "artifacts": items[3:6] if len(items) > 3 else [],
            "flex_slot": None,
        }

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
