"""
Item Delta Value Calculator
==============================
从对局数据中计算装备对排名的影响值 (delta_rank)，写入 tft.db 的 item_stats 表。

Delta 计算:
  delta = avg_placement(有装备) - avg_placement(无装备)
  负值 = 有该装备时排名更好 (placement 越小越好)

两种粒度:
  1. 全局 delta: 该装备在所有英雄上的整体影响 (champion_id = NULL)
  2. 英雄级 delta: 该装备在特定英雄身上的影响 (champion_id = 具体 ID)

过滤:
  - 最少 MIN_SAMPLE 次出场
  - 只计算 items 表中存在的装备

用法:
  uv run python data_collection/scripts/calc_item_delta.py [--min-sample N]

依赖: 无额外依赖
"""

import csv
import sqlite3
import argparse
from pathlib import Path
from collections import defaultdict

# === Paths ===
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CLEANED_DIR = PROJECT_ROOT / "data_collection" / "data" / "cleaned"
DB_PATH = PROJECT_ROOT / "data" / "tft.db"

# === Config ===
MIN_SAMPLE = 10


def load_participants():
    """Load all participants with their placement."""
    path = CLEANED_DIR / "participants.csv"
    participants = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            participants.append({
                "match_id": row["match_id"],
                "puuid": row["puuid"],
                "placement": int(row["placement"]),
            })
    return participants


def load_items(valid_item_ids: set):
    """Load all item assignments: (match_id, puuid, character_id, item_name)."""
    path = CLEANED_DIR / "items.csv"
    items = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["item_name"] in valid_item_ids:
                items.append({
                    "match_id": row["match_id"],
                    "puuid": row["puuid"],
                    "placement": int(row["placement"]),
                    "character_id": row["character_id"],
                    "item_name": row["item_name"],
                })
    return items


def calc_global_delta(participants, items, min_sample):
    """
    Calculate global delta for each item.

    For each item i:
      with_i = avg placement of all players who had item i on any champion
      without_i = avg placement of all players who did NOT have item i
      delta = with_i - without_i
    """
    # Build set of (match_id, puuid) that have each item
    item_players = defaultdict(set)  # item_name → set of (match_id, puuid)
    for it in items:
        item_players[it["item_name"]].add((it["match_id"], it["puuid"]))

    # Overall avg placement
    total_players = len(participants)
    overall_avg = sum(p["placement"] for p in participants) / total_players

    results = []
    for item_name, players in item_players.items():
        with_list = []
        without_list = []
        for p in participants:
            key = (p["match_id"], p["puuid"])
            if key in players:
                with_list.append(p["placement"])
            else:
                without_list.append(p["placement"])

        if len(with_list) < min_sample or len(without_list) < min_sample:
            continue

        avg_with = sum(with_list) / len(with_list)
        avg_without = sum(without_list) / len(without_list)
        delta = avg_with - avg_without

        results.append({
            "item_id": item_name,
            "champion_id": None,
            "delta_rank": round(delta, 4),
            "sample_size": len(with_list),
            "avg_with": round(avg_with, 2),
            "avg_without": round(avg_without, 2),
        })

    results.sort(key=lambda x: x["delta_rank"])
    return results


def calc_champion_delta(items, min_sample):
    """
    Calculate champion-specific delta for each (item, champion) pair.

    For each champion c and item i:
      with_i = avg placement when champion c carries item i
      without_i = avg placement when champion c does NOT carry item i
      delta = with_i - without_i
    """
    # Build per-champion data
    # champ_placements: champion_id → [(match_id, puuid, placement)]
    champ_placements = defaultdict(list)
    # champ_item: (champion_id, item_name) → set of (match_id, puuid)
    champ_item_players = defaultdict(set)

    for it in items:
        cid = it["character_id"]
        key = (it["match_id"], it["puuid"])
        champ_placements[cid].append((key, it["placement"]))
        champ_item_players[(cid, it["item_name"])].add(key)

    results = []
    # For each champion that appears enough
    for cid, placements in champ_placements.items():
        if len(placements) < min_sample:
            continue

        # Get all (match_id, puuid) for this champion
        champ_keys = set(k for k, _ in placements)
        champ_avg = sum(p for _, p in placements) / len(placements)

        # For each item this champion has carried
        items_carried = set()
        for (k, item_name) in champ_item_players:
            if k == cid:
                items_carried.add(item_name)

        for item_name in items_carried:
            with_keys = champ_item_players[(cid, item_name)]
            with_list = [p for k, p in placements if k in with_keys]
            without_list = [p for k, p in placements if k not in with_keys]

            if len(with_list) < min_sample or len(without_list) < min_sample:
                continue

            avg_with = sum(with_list) / len(with_list)
            avg_without = sum(without_list) / len(without_list)
            delta = avg_with - avg_without

            results.append({
                "item_id": item_name,
                "champion_id": cid,
                "delta_rank": round(delta, 4),
                "sample_size": len(with_list),
            })

    results.sort(key=lambda x: x["delta_rank"])
    return results


def main():
    parser = argparse.ArgumentParser(description="Item Delta Calculator")
    parser.add_argument("--min-sample", type=int, default=MIN_SAMPLE,
                        help=f"Minimum sample size (default: {MIN_SAMPLE})")
    args = parser.parse_args()
    min_sample = args.min_sample

    print("=" * 55)
    print("  Item Delta Value Calculator")
    print(f"  DB: {DB_PATH}")
    print(f"  Min sample: {min_sample}")
    print("=" * 55)

    # Load valid item IDs from DB
    conn = sqlite3.connect(str(DB_PATH))
    valid_items = set(r[0] for r in conn.execute("SELECT id FROM items").fetchall())
    print(f"\nValid items in DB: {len(valid_items)}")

    # Load data
    participants = load_participants()
    items = load_items(valid_items)
    print(f"Participants: {len(participants)}")
    print(f"Item rows (valid items only): {len(items)}")

    # Clear existing stats
    conn.execute("DELETE FROM item_stats")
    conn.commit()

    # === Global delta ===
    print("\n--- Global Delta ---")
    global_results = calc_global_delta(participants, items, min_sample)
    print(f"  Items with enough data: {len(global_results)}")

    for r in global_results:
        conn.execute(
            "INSERT OR REPLACE INTO item_stats (item_id, champion_id, delta_rank, sample_size) VALUES (?, ?, ?, ?)",
            (r["item_id"], r["champion_id"], r["delta_rank"], r["sample_size"]),
        )

    # Print top 10 best and worst
    print("\n  Top 10 (best delta, most negative):")
    for r in global_results[:10]:
        sign = "+" if r["delta_rank"] > 0 else ""
        print(f"    {r['item_id']:40s}  delta={sign}{r['delta_rank']:.3f}  n={r['sample_size']}  avg_with={r['avg_with']:.1f}")

    print("\n  Bottom 10 (worst delta, most positive):")
    for r in global_results[-10:]:
        sign = "+" if r["delta_rank"] > 0 else ""
        print(f"    {r['item_id']:40s}  delta={sign}{r['delta_rank']:.3f}  n={r['sample_size']}  avg_with={r['avg_with']:.1f}")

    # === Champion-specific delta ===
    print("\n--- Champion-Specific Delta ---")
    champ_results = calc_champion_delta(items, min_sample)
    print(f"  (Item, Champion) pairs with enough data: {len(champ_results)}")

    for r in champ_results:
        conn.execute(
            "INSERT OR REPLACE INTO item_stats (item_id, champion_id, delta_rank, sample_size) VALUES (?, ?, ?, ?)",
            (r["item_id"], r["champion_id"], r["delta_rank"], r["sample_size"]),
        )

    # Print sample
    print("\n  Sample champion-item deltas:")
    for r in champ_results[:10]:
        sign = "+" if r["delta_rank"] > 0 else ""
        print(f"    {r['champion_id']:30s} + {r['item_id']:40s}  delta={sign}{r['delta_rank']:.3f}  n={r['sample_size']}")

    conn.commit()

    # === Summary ===
    total = conn.execute("SELECT COUNT(*) FROM item_stats").fetchone()[0]
    global_n = conn.execute("SELECT COUNT(*) FROM item_stats WHERE champion_id IS NULL").fetchone()[0]
    champ_n = conn.execute("SELECT COUNT(*) FROM item_stats WHERE champion_id IS NOT NULL").fetchone()[0]

    print(f"\n{'='*55}")
    print(f"  item_stats summary:")
    print(f"    Global entries:        {global_n}")
    print(f"    Champion-specific:     {champ_n}")
    print(f"    Total:                 {total}")
    print(f"{'='*55}")

    conn.close()
    print(f"\nDone!")


if __name__ == "__main__":
    main()
