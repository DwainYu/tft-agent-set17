"""
TFT Match Details Fetcher (SQLite Storage)
==========================================
从 match_ids 文件读取对局 ID，批量拉取对局详情，存入 SQLite。

SQLite 是原始对局数据的最终存储形态：
  - 保留完整 JSON（raw_json 列）
  - 提取关键字段便于索引和查询
  - 支持增量插入（断点续传）
  - pandas 可直接 pd.read_sql() 读取

用法:
  # 从 match_ids JSON 文件拉取
  uv run python data_collection/scripts/fetch_match_details.py

  # 指定输入文件
  uv run python data_collection/scripts/fetch_match_details.py --input data/raw/match_ids_xxx.json

  # 限制拉取数量（调试用）
  uv run python data_collection/scripts/fetch_match_details.py --limit 10

  # 从已有 matches_raw.json 导入到 SQLite
  uv run python data_collection/scripts/fetch_match_details.py --import-json data/raw/matches_raw.json

依赖: aiohttp, python-dotenv
"""

import asyncio
import aiohttp
import json
import os
import sys
import sqlite3
import time
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# === Paths ===
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RAW_DIR = SCRIPT_DIR.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# === Config ===
load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    print("[ERROR] API_KEY not found in .env")
    sys.exit(1)

REGIONAL = "asia"
BASE_URL = f"https://{REGIONAL}.api.riotgames.com"
HEADERS = {"X-Riot-Token": API_KEY}
CST = timezone(timedelta(hours=8))


# ============================================================
#  SQLite Schema
# ============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    match_id            TEXT PRIMARY KEY,
    raw_json            TEXT NOT NULL,
    game_datetime       INTEGER,
    game_date           TEXT,
    queue_id            INTEGER,
    duration_sec        REAL,
    set_number          INTEGER,
    game_type           TEXT,
    participant_count   INTEGER,
    fetched_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS participants (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id            TEXT NOT NULL REFERENCES matches(match_id),
    puuid               TEXT NOT NULL,
    riot_id             TEXT,
    placement           INTEGER,
    win                 INTEGER,
    level               INTEGER,
    gold_left           INTEGER,
    last_round          INTEGER,
    total_damage        INTEGER,
    players_eliminated  INTEGER,
    time_eliminated     REAL,
    trait_count         INTEGER,
    unit_count          INTEGER
);

CREATE INDEX IF NOT EXISTS idx_participants_match ON participants(match_id);
CREATE INDEX IF NOT EXISTS idx_participants_puuid ON participants(puuid);
CREATE INDEX IF NOT EXISTS idx_participants_placement ON participants(placement);
CREATE INDEX IF NOT EXISTS idx_matches_queue ON matches(queue_id);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(game_date);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite connection and create tables."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")       # better concurrent read/write
    conn.execute("PRAGMA synchronous=NORMAL")     # faster writes
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def get_fetched_ids(conn: sqlite3.Connection) -> set[str]:
    """Return set of match_ids already in the database."""
    cursor = conn.execute("SELECT match_id FROM matches")
    return {row[0] for row in cursor}


# ============================================================
#  Rate Limiter
# ============================================================

class RateLimiter:
    def __init__(self):
        self.timestamps: list[float] = []
        self.per_sec_max = 18
        self.per_2min_max = 95

    async def wait(self):
        while True:
            now = time.monotonic()
            self.timestamps = [t for t in self.timestamps if now - t < 120]

            if len(self.timestamps) >= self.per_2min_max:
                wait = self.timestamps[0] + 120 - now + 0.5
                if wait > 0:
                    print(f"    [rate-limit] 2min cap, wait {wait:.1f}s")
                    await asyncio.sleep(wait)
                    continue

            recent = [t for t in self.timestamps if now - t < 1.0]
            if len(recent) >= self.per_sec_max:
                await asyncio.sleep(0.15)
                continue

            self.timestamps.append(time.monotonic())
            return


LIMITER = RateLimiter()


# ============================================================
#  HTTP Fetch
# ============================================================

async def fetch_match(session: aiohttp.ClientSession, match_id: str, retries: int = 3) -> dict | None:
    """Fetch a single match detail with rate limiting and retry."""
    await LIMITER.wait()
    url = f"{BASE_URL}/tft/match/v1/matches/{match_id}"
    for attempt in range(retries):
        try:
            async with session.get(url, params={}, headers=HEADERS,
                                   timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    print(f"    [429] rate limited, retry after {retry_after}s")
                    await asyncio.sleep(retry_after + 1)
                elif resp.status == 404:
                    return None
                else:
                    text = await resp.text()
                    print(f"    [ERROR] {resp.status}: {text[:200]}")
                    return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"    [ERROR] {type(e).__name__}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2)
    return None


# ============================================================
#  Data Extraction
# ============================================================

def extract_match_row(data: dict) -> tuple[dict, list[dict]]:
    """Extract structured rows from raw match JSON."""
    info = data.get("info", {})
    meta = data.get("metadata", {})
    match_id = meta.get("match_id", str(info.get("gameId", "")))

    game_dt = info.get("game_datetime", 0)
    game_date = ""
    if game_dt:
        game_date = datetime.fromtimestamp(game_dt / 1000, tz=CST).strftime("%Y-%m-%d %H:%M:%S")

    match_row = {
        "match_id": match_id,
        "raw_json": json.dumps(data, ensure_ascii=False),
        "game_datetime": game_dt,
        "game_date": game_date,
        "queue_id": info.get("queue_id"),
        "duration_sec": round(info.get("game_length", 0), 1),
        "set_number": info.get("tft_set_number"),
        "game_type": info.get("tft_game_type"),
        "participant_count": len(info.get("participants", [])),
        "fetched_at": datetime.now(CST).isoformat(),
    }

    participant_rows = []
    for p in info.get("participants", []):
        game_name = p.get("riotIdGameName", "")
        tagline = p.get("riotIdTagline", "")
        participant_rows.append({
            "match_id": match_id,
            "puuid": p.get("puuid", ""),
            "riot_id": f"{game_name}#{tagline}" if game_name else "",
            "placement": p.get("placement", 0),
            "win": int(p.get("win", False)),
            "level": p.get("level", 0),
            "gold_left": p.get("gold_left", 0),
            "last_round": p.get("last_round", 0),
            "total_damage": p.get("total_damage_to_players", 0),
            "players_eliminated": p.get("players_eliminated", 0),
            "time_eliminated": round(p.get("time_eliminated", 0), 1),
            "trait_count": len(p.get("traits", [])),
            "unit_count": len(p.get("units", [])),
        })

    return match_row, participant_rows


def insert_match(conn: sqlite3.Connection, match_row: dict, participant_rows: list[dict]):
    """Insert a match and its participants into SQLite."""
    conn.execute("""
        INSERT OR REPLACE INTO matches
            (match_id, raw_json, game_datetime, game_date, queue_id,
             duration_sec, set_number, game_type, participant_count, fetched_at)
        VALUES (:match_id, :raw_json, :game_datetime, :game_date, :queue_id,
                :duration_sec, :set_number, :game_type, :participant_count, :fetched_at)
    """, match_row)

    # delete old participants if re-inserting
    conn.execute("DELETE FROM participants WHERE match_id = ?", (match_row["match_id"],))

    for p in participant_rows:
        conn.execute("""
            INSERT INTO participants
                (match_id, puuid, riot_id, placement, win, level, gold_left,
                 last_round, total_damage, players_eliminated, time_eliminated,
                 trait_count, unit_count)
            VALUES (:match_id, :puuid, :riot_id, :placement, :win, :level, :gold_left,
                    :last_round, :total_damage, :players_eliminated, :time_eliminated,
                    :trait_count, :unit_count)
        """, p)

    conn.commit()


# ============================================================
#  Batch Fetch
# ============================================================

async def batch_fetch(match_ids: list[str], conn: sqlite3.Connection, limit: int | None = None):
    """Fetch match details in batch and store in SQLite."""
    to_fetch = match_ids[:limit] if limit else match_ids
    already = get_fetched_ids(conn)
    todo = [mid for mid in to_fetch if mid not in already]

    print(f"  Total match IDs:  {len(to_fetch)}")
    print(f"  Already in DB:    {len(to_fetch) - len(todo)}")
    print(f"  To fetch:         {len(todo)}")

    if not todo:
        print("  Nothing to do.")
        return

    fetched = 0
    errors = 0
    t0 = time.monotonic()

    async with aiohttp.ClientSession() as session:
        for i, mid in enumerate(todo):
            data = await fetch_match(session, mid)
            if data:
                match_row, participant_rows = extract_match_row(data)
                insert_match(conn, match_row, participant_rows)
                fetched += 1
            else:
                errors += 1

            done = i + 1
            if done % 10 == 0 or done == len(todo):
                elapsed = time.monotonic() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(todo) - done) / rate if rate > 0 else 0
                print(f"  [{done:4d}/{len(todo)}] ok={fetched} err={errors} "
                      f"rate={rate:.1f}/s ETA={eta:.0f}s")

    print(f"\n  Done: {fetched} fetched, {errors} errors")


# ============================================================
#  Import from JSON
# ============================================================

def import_from_json(json_path: Path, conn: sqlite3.Connection):
    """Import matches from an existing matches_raw.json into SQLite."""
    print(f"  Loading {json_path} ...")
    with open(json_path, "r", encoding="utf-8") as f:
        matches = json.load(f)

    already = get_fetched_ids(conn)
    imported = 0
    for data in matches:
        meta = data.get("metadata", {})
        mid = meta.get("match_id", str(data.get("info", {}).get("gameId", "")))
        if mid in already:
            continue
        match_row, participant_rows = extract_match_row(data)
        insert_match(conn, match_row, participant_rows)
        imported += 1

    print(f"  Imported {imported} matches ({len(already)} already existed)")


# ============================================================
#  DB Summary
# ============================================================

def print_db_summary(conn: sqlite3.Connection):
    """Print a summary of what's in the database."""
    total = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    part = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
    queues = conn.execute(
        "SELECT queue_id, COUNT(*) FROM matches GROUP BY queue_id ORDER BY COUNT(*) DESC"
    ).fetchall()
    dates = conn.execute(
        "SELECT MIN(game_date), MAX(game_date) FROM matches"
    ).fetchone()

    print(f"\n{'='*60}")
    print(f"  SQLite Database Summary")
    print(f"{'='*60}")
    print(f"  Matches:        {total}")
    print(f"  Participants:   {part}")
    print(f"  Date range:     {dates[0]} ~ {dates[1]}")
    print(f"  Queue IDs:      {dict(queues)}")
    print(f"{'='*60}")


# ============================================================
#  Main
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="TFT Match Details Fetcher (SQLite)")
    parser.add_argument("--input", type=str, help="Path to match_ids JSON file (auto-detect if omitted)")
    parser.add_argument("--limit", type=int, help="Max matches to fetch")
    parser.add_argument("--import-json", type=str, help="Import from matches_raw.json into SQLite")
    parser.add_argument("--db", type=str, help="SQLite DB path (auto-generated if omitted)")
    parser.add_argument("--summary", action="store_true", help="Print DB summary and exit")
    return parser.parse_args()


def find_match_ids_file() -> Path:
    """Auto-detect match_ids JSON file in raw dir."""
    candidates = sorted(RAW_DIR.glob("match_ids*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        print("[ERROR] No match_ids*.json found in", RAW_DIR)
        sys.exit(1)
    return candidates[0]


def derive_db_name(ids_file: Path) -> Path:
    """Derive SQLite DB name from the match_ids file name.
    e.g. match_ids_jp1_asia_20260711_20260713.json
       → matches_jp1_asia_20260711_20260713.db
    """
    stem = ids_file.stem  # e.g. match_ids_jp1_asia_20260711_20260713
    db_stem = stem.replace("match_ids", "matches", 1)
    return RAW_DIR / f"{db_stem}.db"


async def main():
    args = parse_args()

    # Determine input file
    ids_file = Path(args.input) if args.input else find_match_ids_file()
    print(f"[Input]  {ids_file}")

    # Determine DB path
    db_path = Path(args.db) if args.db else derive_db_name(ids_file)
    print(f"[Output] {db_path}")

    conn = init_db(db_path)

    # --summary: just print and exit
    if args.summary:
        print_db_summary(conn)
        conn.close()
        return

    # --import-json: import from existing JSON
    if args.import_json:
        import_from_json(Path(args.import_json), conn)
        print_db_summary(conn)
        conn.close()
        return

    # Normal fetch mode: load match IDs
    with open(ids_file, "r", encoding="utf-8") as f:
        ids_data = json.load(f)
    match_ids = ids_data.get("ids", [])
    print(f"[IDs]    {len(match_ids)} match IDs loaded")

    t0 = time.monotonic()
    await batch_fetch(match_ids, conn, limit=args.limit)

    elapsed = time.monotonic() - t0
    print(f"  Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")

    print_db_summary(conn)
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
