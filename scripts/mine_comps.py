"""Mine compositions from cleaned match data and populate the comps tables.

Usage:
    python scripts/mine_comps.py [--min-samples 3] [--top-n 4]

Reads:
    data_collection/data/cleaned/units.csv
    data_collection/data/cleaned/traits.csv
    data_collection/data/cleaned/participants.csv

Writes to:
    data/tft.db  (comps + comp_champions tables)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tft.db"
DATA_DIR = Path(__file__).resolve().parent.parent / "data_collection" / "data" / "cleaned"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS comps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    anchor_id       TEXT NOT NULL,
    avg_placement   REAL,
    sample_size     INTEGER,
    top_traits      TEXT,          -- JSON array of trait name_zh
    patch           TEXT,
    FOREIGN KEY (anchor_id) REFERENCES champions(id)
);

CREATE TABLE IF NOT EXISTS comp_champions (
    comp_id     INTEGER NOT NULL,
    champion_id TEXT NOT NULL,
    role        TEXT,              -- 主C / 副C / 坦克 / 辅助 / 灵活位
    avg_stars   REAL,
    pick_rate   REAL,              -- fraction of boards in this comp that include this champ
    PRIMARY KEY (comp_id, champion_id),
    FOREIGN KEY (comp_id) REFERENCES comps(id),
    FOREIGN KEY (champion_id) REFERENCES champions(id)
);
"""


# ---------------------------------------------------------------------------
# Mining logic
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    units = pd.read_csv(DATA_DIR / "units.csv")
    traits = pd.read_csv(DATA_DIR / "traits.csv")
    participants = pd.read_csv(DATA_DIR / "participants.csv")
    return units, traits, participants


def get_champion_costs(conn: sqlite3.Connection) -> dict[str, int]:
    """Return {champion_id: cost} from the DB."""
    rows = conn.execute("SELECT id, cost FROM champions").fetchall()
    return {r[0]: r[1] for r in rows}


def get_trait_names(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {trait_id: name_zh} from the DB."""
    rows = conn.execute("SELECT id, name_zh FROM traits").fetchall()
    return {r[0]: r[1] for r in rows}


def get_champion_traits(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Return {champion_id: [trait_id, ...]}."""
    rows = conn.execute("SELECT champion_id, trait_id FROM champion_traits").fetchall()
    result: dict[str, list[str]] = {}
    for champ, trait in rows:
        result.setdefault(champ, []).append(trait)
    return result


def mine_comps(
    units: pd.DataFrame,
    traits_df: pd.DataFrame,
    costs: dict[str, int],
    min_samples: int = 3,
    top_n: int = 4,
) -> list[dict]:
    """Extract composition clusters from top-N placement boards.

    Strategy:
    1. Filter boards with placement <= top_n.
    2. For each board, extract "core" champions (cost >= 3).
    3. Group boards by their core set (frozenset of core champ IDs).
    4. For groups with >= min_samples boards, build a comp entry.
    5. Full champion list = most common champions across the group's boards.
    """
    # Filter top-N boards
    top = units[units.placement <= top_n].copy()

    # Add cost column
    top["cost"] = top.character_id.map(costs).fillna(0).astype(int)

    # Group by (match_id, player_id) → one board per group
    boards: list[dict] = []
    for (mid, pid), grp in top.groupby(["match_id", "player_id"]):
        champs = list(grp.character_id.unique())
        placement = grp.placement.iloc[0]
        core = frozenset(c for c in champs if costs.get(c, 0) >= 3)
        if len(core) < 2:
            continue  # skip boards without enough high-cost units
        boards.append({
            "match_id": mid,
            "player_id": pid,
            "placement": placement,
            "champions": champs,
            "core": core,
        })

    # Group by core composition
    core_groups: dict[frozenset, list[dict]] = {}
    for b in boards:
        core_groups.setdefault(b["core"], []).append(b)

    # Also try merging similar cores (Jaccard >= 0.6)
    # Simple greedy merge: for each core, find the best matching existing cluster
    merged: dict[frozenset, list[dict]] = {}
    for core, group in sorted(core_groups.items(), key=lambda x: -len(x[1])):
        best_match = None
        best_score = 0.0
        for existing_core in merged:
            intersection = len(core & existing_core)
            union = len(core | existing_core)
            jaccard = intersection / union if union > 0 else 0
            if jaccard > best_score:
                best_score = jaccard
                best_match = existing_core
        if best_match is not None and best_score >= 0.5:
            merged[best_match].extend(group)
        else:
            merged[core] = list(group)

    # Build comp entries
    comps: list[dict] = []
    for core, group in merged.items():
        if len(group) < min_samples:
            continue

        # Count champion frequency across all boards in this cluster
        champ_counter: Counter = Counter()
        star_accum: dict[str, list[int]] = {}
        for b in group:
            for c in b["champions"]:
                champ_counter[c] += 1
                # Get star levels for this champ in this board
                board_units = units[
                    (units.match_id == b["match_id"])
                    & (units.player_id == b["player_id"])
                    & (units.character_id == c)
                ]
                if not board_units.empty:
                    star_accum.setdefault(c, []).append(
                        board_units.star_level.max()
                    )

        n_boards = len(group)
        avg_placement = sum(b["placement"] for b in group) / n_boards

        # Select champions that appear in >= 40% of boards
        threshold = max(2, int(n_boards * 0.4))
        comp_champs = [
            c for c, cnt in champ_counter.most_common()
            if cnt >= threshold
        ][:9]  # cap at 9 champions

        if len(comp_champs) < 4:
            continue  # not enough champions for a real comp

        # Determine anchor: highest-cost champion in the core
        anchor = max(core, key=lambda c: costs.get(c, 0))

        # Compute active traits from the comp's champion set
        comp_traits = compute_traits(comp_champs, costs)

        comps.append({
            "anchor_id": anchor,
            "avg_placement": round(avg_placement, 2),
            "sample_size": n_boards,
            "champions": comp_champs,
            "champ_stats": {
                c: {
                    "pick_rate": round(champ_counter[c] / n_boards, 2),
                    "avg_stars": round(
                        sum(star_accum.get(c, [1])) / max(len(star_accum.get(c, [1])), 1), 1
                    ),
                }
                for c in comp_champs
            },
            "traits": comp_traits,
        })

    # Sort by sample_size desc, then avg_placement asc
    comps.sort(key=lambda c: (-c["sample_size"], c["avg_placement"]))
    return comps


def compute_traits(
    champ_ids: list[str],
    costs: dict[str, int],
) -> list[str]:
    """Compute which traits are "active" given a set of champions.

    A trait is active if the number of champions with that trait meets
    the minimum threshold (typically 2+ for most traits).
    Returns trait IDs sorted by count descending.
    """
    # This is a simplified version — real trait thresholds vary per trait
    # For now, count trait occurrences and return traits with 2+ champions
    conn = sqlite3.connect(DB_PATH)
    champ_traits = get_champion_traits(conn)
    conn.close()

    trait_counter: Counter = Counter()
    for cid in champ_ids:
        for tid in champ_traits.get(cid, []):
            trait_counter[tid] += 1

    # Return traits with 2+ champions (active threshold)
    return [tid for tid, cnt in trait_counter.most_common() if cnt >= 2]


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------

def write_comps(comps: list[dict], conn: sqlite3.Connection, trait_names: dict[str, str]) -> None:
    """Write mined comps to the database."""
    conn.executescript(SCHEMA_SQL)

    # Clear existing data
    conn.execute("DELETE FROM comp_champions")
    conn.execute("DELETE FROM comps")

    for comp in comps:
        # Build comp name from anchor champion
        anchor_row = conn.execute(
            "SELECT name_zh FROM champions WHERE id = ?", (comp["anchor_id"],)
        ).fetchone()
        anchor_name = anchor_row[0] if anchor_row else comp["anchor_id"]

        # Resolve trait names
        trait_zh = [trait_names.get(t, t) for t in comp["traits"][:6]]

        cur = conn.execute(
            "INSERT INTO comps (name, anchor_id, avg_placement, sample_size, top_traits, patch) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"{anchor_name} 核心阵容",
                comp["anchor_id"],
                comp["avg_placement"],
                comp["sample_size"],
                json.dumps(trait_zh, ensure_ascii=False),
                "16.13",
            ),
        )
        comp_id = cur.lastrowid

        # Determine roles
        champ_costs = {}
        for cid in comp["champions"]:
            row = conn.execute("SELECT cost FROM champions WHERE id = ?", (cid,)).fetchone()
            champ_costs[cid] = row[0] if row else 1

        for cid in comp["champions"]:
            cost = champ_costs.get(cid, 1)
            stats = comp["champ_stats"].get(cid, {})
            pick_rate = stats.get("pick_rate", 0)

            # Simple role assignment
            if cid == comp["anchor_id"]:
                role = "主C"
            elif cost >= 4 and pick_rate >= 0.6:
                role = "副C"
            elif cost <= 2:
                role = "辅助"
            elif cost == 3:
                role = "坦克"
            else:
                role = "灵活位"

            conn.execute(
                "INSERT INTO comp_champions (comp_id, champion_id, role, avg_stars, pick_rate) "
                "VALUES (?, ?, ?, ?, ?)",
                (comp_id, cid, role, stats.get("avg_stars", 1.0), pick_rate),
            )

    conn.commit()
    print(f"Wrote {len(comps)} compositions to database.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Mine comps from match data")
    parser.add_argument("--min-samples", type=int, default=3, help="Min boards per comp cluster")
    parser.add_argument("--top-n", type=int, default=4, help="Only consider placement <= N")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    costs = get_champion_costs(conn)
    trait_names = get_trait_names(conn)

    units, traits_df, participants = load_data()
    print(f"Loaded {len(units)} unit records, {len(traits_df)} trait records")

    comps = mine_comps(units, traits_df, costs, args.min_samples, args.top_n)
    print(f"Mined {len(comps)} composition clusters")

    for i, c in enumerate(comps[:10]):
        anchor_row = conn.execute(
            "SELECT name_zh FROM champions WHERE id = ?", (c["anchor_id"],)
        ).fetchone()
        anchor_name = anchor_row[0] if anchor_row else c["anchor_id"]
        print(
            f"  {i+1}. {anchor_name} | avg={c['avg_placement']:.1f} "
            f"n={c['sample_size']} champs={len(c['champions'])} "
            f"traits={len(c['traits'])}"
        )

    write_comps(comps, conn, trait_names)
    conn.close()


if __name__ == "__main__":
    main()
