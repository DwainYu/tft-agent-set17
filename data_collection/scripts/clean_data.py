"""
TFT Match Data Cleaner
========================
将 matches_raw.json 清洗为多张 CSV 平表，供后续分析使用。

输出:
  cleaned/matches.csv      — 对局维度（427 行）
  cleaned/participants.csv — 玩家×对局维度（3416 行）
  cleaned/units.csv        — 棋子维度（~30000 行）
  cleaned/traits.csv       — 羁绊维度（~40000 行）
  cleaned/items.csv        — 装备维度（~50000 行）
  cleaned/cleaning_report.json — 清洗报告

过滤规则:
  1. 仅保留 queue_id=1100 (Ranked TFT)
  2. 排除 participants < 8 的对局
  3. 排除 game_length < 300s (5分钟) 的异常对局
  4. 标记 trait.style=0 的为未激活羁绊
"""

import json
import csv
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter

CST = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).resolve().parent          # data_collection/scripts/
DATA_DIR = SCRIPT_DIR.parent / "data" / "raw"         # data_collection/data/raw/
CLEANED_DIR = SCRIPT_DIR.parent / "data" / "cleaned"  # data_collection/data/cleaned/
CLEANED_DIR.mkdir(parents=True, exist_ok=True)

# === Load Raw Data ===
import sqlite3
import glob

# Auto-detect SQLite DB
db_files = sorted(glob.glob(str(DATA_DIR / "*.db")))
if not db_files:
    raise FileNotFoundError(f"No .db files found in {DATA_DIR}")
db_path = db_files[-1]  # use latest DB
print(f"Loading from SQLite: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.execute("SELECT raw_json FROM matches")
raw_matches = []
for (raw_json,) in cursor:
    raw_matches.append(json.loads(raw_json))
conn.close()
print(f"  Loaded {len(raw_matches)} matches")

# === Filter ===
report = {
    "raw_total": len(raw_matches),
    "filtered": {"queue": 0, "participants": 0, "duration": 0},
    "kept": 0,
}

filtered_matches = []
for m in raw_matches:
    info = m["info"]
    qid = info.get("queue_id")
    npart = len(info.get("participants", []))
    duration = info.get("game_length", 0)

    if qid != 1100:
        report["filtered"]["queue"] += 1
        continue
    if npart < 8:
        report["filtered"]["participants"] += 1
        continue
    if duration < 300:
        report["filtered"]["duration"] += 1
        continue

    filtered_matches.append(m)

report["kept"] = len(filtered_matches)
print(f"\nFilter results:")
print(f"  Removed (non-ranked):   {report['filtered']['queue']}")
print(f"  Removed (<8 players):   {report['filtered']['participants']}")
print(f"  Removed (<5min):        {report['filtered']['duration']}")
print(f"  Kept:                   {report['kept']}")

# === Helper ===
def parse_version(v: str) -> str:
    """Extract clean version from build string like 'Linux Version 16.13.791.5903 ...'"""
    if not v:
        return ""
    parts = v.split()
    for p in parts:
        if p[0].isdigit() and "." in p:
            return p.rstrip(".")
    return v

def ts_to_cst(ts_ms: int) -> str:
    """Convert epoch ms to CST datetime string"""
    if not ts_ms:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000, tz=CST).strftime("%Y-%m-%d %H:%M:%S")

# === Extract Tables ===
print("\nExtracting tables ...")

matches_rows = []
participants_rows = []
units_rows = []
traits_rows = []
items_rows = []

for m in filtered_matches:
    info = m["info"]
    meta = m.get("metadata", {})
    match_id = meta.get("match_id", info.get("gameId", ""))
    game_dt = info.get("game_datetime", 0)
    version = parse_version(info.get("game_version", ""))
    duration = round(info.get("game_length", 0), 1)

    matches_rows.append({
        "match_id": match_id,
        "game_datetime": ts_to_cst(game_dt),
        "game_date": ts_to_cst(game_dt)[:10] if game_dt else "",
        "duration_sec": duration,
        "duration_min": round(duration / 60, 1),
        "version": version,
        "queue_id": info.get("queue_id"),
        "tft_set_number": info.get("tft_set_number"),
        "tft_game_type": info.get("tft_game_type"),
    })

    for p in info.get("participants", []):
        puuid = p.get("puuid", "")
        game_name = p.get("riotIdGameName", "")
        tagline = p.get("riotIdTagline", "")
        placement = p.get("placement", 0)
        level = p.get("level", 0)
        gold_left = p.get("gold_left", 0)
        last_round = p.get("last_round", 0)
        win = p.get("win", False)
        damage = p.get("total_damage_to_players", 0)
        eliminated = p.get("players_eliminated", 0)
        time_elim = round(p.get("time_eliminated", 0), 1)

        participants_rows.append({
            "match_id": match_id,
            "puuid": puuid,
            "game_name": game_name,
            "tagline": tagline,
            "player_id": f"{game_name}#{tagline}" if game_name else puuid[:12],
            "placement": placement,
            "win": win,
            "level": level,
            "gold_left": gold_left,
            "last_round": last_round,
            "total_damage": damage,
            "players_eliminated": eliminated,
            "time_eliminated_sec": time_elim,
        })

        # Units
        for u in p.get("units", []):
            char_id = u.get("character_id", "")
            star = u.get("tier", 0)
            item_names = u.get("itemNames", [])

            units_rows.append({
                "match_id": match_id,
                "puuid": puuid,
                "player_id": f"{game_name}#{tagline}" if game_name else puuid[:12],
                "placement": placement,
                "character_id": char_id,
                "star_level": star,
                "item_count": len(item_names),
            })

            # Items (one row per item)
            for item_name in item_names:
                items_rows.append({
                    "match_id": match_id,
                    "puuid": puuid,
                    "player_id": f"{game_name}#{tagline}" if game_name else puuid[:12],
                    "placement": placement,
                    "character_id": char_id,
                    "item_name": item_name,
                })

        # Traits
        for t in p.get("traits", []):
            trait_name = t.get("name", "")
            tier_cur = t.get("tier_current", 0)
            tier_total = t.get("tier_total", 0)
            style = t.get("style", 0)

            traits_rows.append({
                "match_id": match_id,
                "puuid": puuid,
                "player_id": f"{game_name}#{tagline}" if game_name else puuid[:12],
                "placement": placement,
                "trait_name": trait_name,
                "tier_current": tier_cur,
                "tier_total": tier_total,
                "style": style,
                "is_active": tier_cur > 0,
            })

# === Write CSVs ===
def write_csv(rows, filename, fieldnames=None):
    if not rows:
        print(f"  [SKIP] {filename}: no rows")
        return
    path = CLEANED_DIR / filename
    keys = fieldnames or list(rows[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  -> {path} ({len(rows)} rows, {path.stat().st_size / 1024:.1f} KB)")

print("\nWriting CSVs ...")
write_csv(matches_rows, "matches.csv")
write_csv(participants_rows, "participants.csv")
write_csv(units_rows, "units.csv")
write_csv(traits_rows, "traits.csv")
write_csv(items_rows, "items.csv")

# === Build Report ===
report["tables"] = {
    "matches": len(matches_rows),
    "participants": len(participants_rows),
    "units": len(units_rows),
    "traits": len(traits_rows),
    "items": len(items_rows),
}

# Quick stats
placements = [r["placement"] for r in participants_rows]
report["stats"] = {
    "placement_dist": {k: v for k, v in sorted(Counter(placements).items())},
    "unique_players": len(set(r["puuid"] for r in participants_rows)),
    "unique_champions": len(set(r["character_id"] for r in units_rows)),
    "unique_traits": len(set(r["trait_name"] for r in traits_rows)),
    "unique_items": len(set(r["item_name"] for r in items_rows)),
    "avg_duration_min": round(sum(r["duration_sec"] for r in matches_rows) / len(matches_rows) / 60, 1) if matches_rows else 0,
}

# Top champions by pick count (per player, not per match)
champ_counter = Counter(r["character_id"] for r in units_rows)
report["stats"]["top_15_champions"] = dict(champ_counter.most_common(15))

# Top active traits
active_traits = [r["trait_name"] for r in traits_rows if r["is_active"]]
report["stats"]["top_15_active_traits"] = dict(Counter(active_traits).most_common(15))

# Top items
report["stats"]["top_15_items"] = dict(Counter(r["item_name"] for r in items_rows).most_common(15))

# Top players by match count
player_match_count = Counter(r["player_id"] for r in participants_rows)
report["stats"]["top_10_players_by_games"] = dict(player_match_count.most_common(10))

# Challenger win rate: placement 1-4 = top 4
top4_count = Counter()
total_games = Counter()
for r in participants_rows:
    pid = r["player_id"]
    total_games[pid] += 1
    if r["placement"] <= 4:
        top4_count[pid] += 1

# Players with >= 10 games
qualified = {pid: (total_games[pid], top4_count[pid], round(top4_count[pid] / total_games[pid] * 100, 1))
             for pid, cnt in total_games.items() if cnt >= 10}
sorted_by_top4 = sorted(qualified.items(), key=lambda x: (-x[1][2], -x[1][0]))
report["stats"]["top_10_top4_rate_10games"] = [
    {"player": pid, "games": g, "top4": t, "top4_rate": f"{r}%"}
    for pid, (g, t, r) in sorted_by_top4[:10]
]

with open(CLEANED_DIR / "cleaning_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"Cleaning Report:")
print(f"  Raw matches:     {report['raw_total']}")
print(f"  Filtered out:    {report['raw_total'] - report['kept']}")
print(f"  Kept (Ranked):   {report['kept']}")
print(f"  Unique players:  {report['stats']['unique_players']}")
print(f"  Unique champs:   {report['stats']['unique_champions']}")
print(f"  Unique traits:   {report['stats']['unique_traits']}")
print(f"  Unique items:    {report['stats']['unique_items']}")
print(f"  Avg duration:    {report['stats']['avg_duration_min']} min")
print(f"{'='*60}")
print(f"\nAll files saved to: {CLEANED_DIR}")
