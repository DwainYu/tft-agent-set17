"""
TFT Challenger Match Data Fetcher
===================================
JP1 Challenger 对局数据采集脚本

流程:
  Step 1: 获取 Challenger 玩家列表 → challengers.json
  Step 2: 获取 match IDs（去重）   → match_ids.json
  Step 3: 获取 match details        → matches_raw.json
  Step 4: 数据概览分析             → data_overview.json

支持断点续传: 已保存的中间结果会被复用,跳过已完成的步骤。

用法:
  python fetch_challenger_matches.py [--max-matches N] [--skip-details]

依赖: aiohttp, python-dotenv
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

# === Paths ===
SCRIPT_DIR = Path(__file__).resolve().parent          # data_collection/scripts/
PROJECT_ROOT = SCRIPT_DIR.parent.parent               # tft-agent-set17/
DATA_DIR = SCRIPT_DIR.parent / "data" / "raw"         # data_collection/data/raw/
DATA_DIR.mkdir(parents=True, exist_ok=True)

# === Configuration ===
load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    print("[ERROR] API_KEY not found in .env")
    sys.exit(1)

PLATFORM = "jp1"
REGIONAL = "asia"  # JP1 → asia regional routing
BASE_PLATFORM = f"https://{PLATFORM}.api.riotgames.com"
BASE_REGIONAL = f"https://{REGIONAL}.api.riotgames.com"

CST = timezone(timedelta(hours=8))
START_TIME = int(datetime(2026, 7, 11, 0, 0, 0, tzinfo=CST).timestamp())
END_TIME   = int(datetime(2026, 7, 13, 23, 59, 59, tzinfo=CST).timestamp())

TARGET_MATCHES = 500
MAX_MATCH_IDS  = 800  # collect extra before dedup
HEADERS = {"X-Riot-Token": API_KEY}


# === Rate Limiter ===
class RateLimiter:
    """
    Riot dev key rate limits:
      - 20 requests per 1 second  (app rate)
      - 100 requests per 120 seconds (method rate)
    """
    def __init__(self):
        self.timestamps: list[float] = []
        self.per_sec_max = 18    # leave headroom from 20
        self.per_2min_max = 95   # leave headroom from 100

    async def wait(self):
        while True:
            now = time.monotonic()
            self.timestamps = [t for t in self.timestamps if now - t < 120]

            # check per-2min limit
            if len(self.timestamps) >= self.per_2min_max:
                wait = self.timestamps[0] + 120 - now + 0.5
                if wait > 0:
                    print(f"    [rate-limit] 2min cap hit, wait {wait:.1f}s ...")
                    await asyncio.sleep(wait)
                    continue

            # check per-1sec limit
            recent = [t for t in self.timestamps if now - t < 1.0]
            if len(recent) >= self.per_sec_max:
                await asyncio.sleep(0.15)
                continue

            self.timestamps.append(time.monotonic())
            return


LIMITER = RateLimiter()


# === HTTP Helpers ===
async def fetch(session: aiohttp.ClientSession, url: str, params: dict, retries: int = 3) -> dict | None:
    """Fetch with rate limiting and retry on 429."""
    await LIMITER.wait()
    for attempt in range(retries):
        try:
            async with session.get(url, params=params, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    print(f"    [429] rate limited, retry after {retry_after}s (attempt {attempt+1})")
                    await asyncio.sleep(retry_after + 1)
                elif resp.status == 404:
                    return None  # expected for some endpoints
                else:
                    text = await resp.text()
                    print(f"    [ERROR] {resp.status}: {text[:200]}")
                    return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"    [ERROR] {type(e).__name__}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2)
    return None


def save_json(data, filename: str):
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  -> saved {path} ({path.stat().st_size / 1024:.1f} KB)")


def load_json(filename: str):
    path = DATA_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# === Step 1: Fetch Challengers ===
async def step1_fetch_challengers():
    cached = load_json("challengers.json")
    if cached:
        print(f"[Step 1] Using cached challengers.json ({cached['count']} players)")
        return cached["puuids"]

    print("[Step 1] Fetching JP1 Challenger list ...")
    async with aiohttp.ClientSession() as session:
        data = await fetch(session, f"{BASE_PLATFORM}/tft/league/v1/challenger",
                           {"queue": "RANKED_TFT"})

    if not data or "entries" not in data:
        print("  [FAIL] could not fetch challenger list")
        sys.exit(1)

    puuids = [e["puuid"] for e in data["entries"]]
    save_json({"count": len(puuids), "puuids": puuids, "fetched_at": datetime.now(CST).isoformat()},
              "challengers.json")
    print(f"  Found {len(puuids)} Challenger players")
    return puuids


# === Step 2: Fetch Match IDs ===
async def step2_fetch_match_ids(puuids: list[str]) -> list[str]:
    cached = load_json("match_ids.json")
    if cached:
        print(f"[Step 2] Using cached match_ids.json ({cached['count']} unique IDs)")
        return cached["ids"]

    print(f"[Step 2] Fetching match IDs for {len(puuids)} players ...")
    print(f"  Time range: {datetime.fromtimestamp(START_TIME, CST)} ~ {datetime.fromtimestamp(END_TIME, CST)}")

    all_ids: list[str] = []
    seen: set[str] = set()
    no_matches = 0

    async with aiohttp.ClientSession() as session:
        for i, puuid in enumerate(puuids):
            result = await fetch(session,
                f"{BASE_REGIONAL}/tft/match/v1/matches/by-puuid/{puuid}/ids",
                {"startTime": START_TIME, "endTime": END_TIME, "count": 100})

            if result and len(result) > 0:
                new = 0
                for mid in result:
                    if mid not in seen:
                        seen.add(mid)
                        all_ids.append(mid)
                        new += 1
                print(f"  [{i+1:3d}/{len(puuids)}] +{new} new (total unique: {len(all_ids)})")
            else:
                no_matches += 1
                print(f"  [{i+1:3d}/{len(puuids)}] no matches")

            # early stop
            if len(all_ids) >= MAX_MATCH_IDS:
                print(f"  Reached {MAX_MATCH_IDS} unique IDs, stopping early")
                break

    print(f"  Done: {len(all_ids)} unique match IDs ({no_matches} players had no matches)")
    save_json({
        "count": len(all_ids),
        "ids": all_ids,
        "fetched_at": datetime.now(CST).isoformat(),
        "time_range": {
            "start": datetime.fromtimestamp(START_TIME, CST).isoformat(),
            "end": datetime.fromtimestamp(END_TIME, CST).isoformat(),
        }
    }, "match_ids.json")
    return all_ids


# === Step 3: Fetch Match Details ===
async def step3_fetch_details(match_ids: list[str], max_matches: int) -> list[dict]:
    ids_to_fetch = match_ids[:max_matches]
    cached = load_json("matches_raw.json")
    cached_map: dict[str, dict] = {}
    if cached:
        cached_map = {m.get("metadata", {}).get("match_id", ""): m for m in cached}
        print(f"[Step 3] Cache has {len(cached_map)} matches already")

    to_fetch = [mid for mid in ids_to_fetch if mid not in cached_map]
    print(f"[Step 3] Fetching {len(to_fetch)} match details (total target: {len(ids_to_fetch)}) ...")

    fetched = 0
    errors = 0
    t0 = time.monotonic()

    async with aiohttp.ClientSession() as session:
        for i, mid in enumerate(to_fetch):
            result = await fetch(session, f"{BASE_REGIONAL}/tft/match/v1/matches/{mid}", {})
            if result:
                cached_map[mid] = result
                fetched += 1
            else:
                errors += 1

            done = i + 1
            if done % 10 == 0 or done == len(to_fetch):
                elapsed = time.monotonic() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(to_fetch) - done) / rate if rate > 0 else 0
                print(f"  [{done:4d}/{len(to_fetch)}] fetched={fetched} errors={errors} "
                      f"rate={rate:.1f}/s ETA={eta:.0f}s")

    # assemble final list in original order
    final = [cached_map[mid] for mid in ids_to_fetch if mid in cached_map]
    print(f"  Done: {len(final)} matches saved")
    save_json(final, "matches_raw.json")
    return final


# === Step 4: Data Overview ===
def step4_overview():
    print("\n[Step 4] Data Overview")
    print("=" * 60)

    matches = load_json("matches_raw.json")
    if not matches:
        print("  No matches data found")
        return

    total = len(matches)
    all_participants = []
    placements = []
    queue_ids = []
    game_lengths = []
    versions = []
    set_numbers = []
    trait_names = []
    character_ids = []
    augments_all = []

    for m in matches:
        info = m.get("info", {})
        queue_ids.append(info.get("queue_id"))
        game_lengths.append(info.get("game_length", 0))
        versions.append(info.get("game_version", ""))
        set_numbers.append(info.get("tft_set_number"))

        for p in info.get("participants", []):
            all_participants.append(p.get("puuid"))
            placements.append(p.get("placement"))
            for t in p.get("traits", []):
                trait_names.append(t.get("name"))
            for u in p.get("units", []):
                character_ids.append(u.get("character_id"))
            for a in p.get("augments", []):
                augments_all.append(a)

    puuid_set = set(all_participants)
    summary = {
        "total_matches": total,
        "unique_players": len(puuid_set),
        "total_participants": len(all_participants),
        "avg_participants_per_match": round(len(all_participants) / total, 1) if total else 0,
        "queue_id_dist": dict(Counter(queue_ids).most_common()),
        "set_number_dist": dict(Counter(set_numbers).most_common()),
        "placement_dist": {k: v for k, v in sorted(Counter(placements).items())},
        "game_length": {
            "min_sec": round(min(game_lengths), 0) if game_lengths else 0,
            "max_sec": round(max(game_lengths), 0) if game_lengths else 0,
            "avg_sec": round(sum(game_lengths) / len(game_lengths), 0) if game_lengths else 0,
            "avg_min": round(sum(game_lengths) / len(game_lengths) / 60, 1) if game_lengths else 0,
        },
        "game_versions": dict(Counter(versions).most_common(5)),
        "unique_traits": len(set(trait_names)),
        "top_traits": dict(Counter(trait_names).most_common(20)),
        "unique_champions": len(set(character_ids)),
        "top_champions": dict(Counter(character_ids).most_common(20)),
        "unique_augments": len(set(augments_all)),
        "top_augments": dict(Counter(augments_all).most_common(20)),
    }

    print(f"\n  Matches:             {summary['total_matches']}")
    print(f"  Unique players:      {summary['unique_players']}")
    print(f"  Avg per match:       {summary['avg_participants_per_match']} participants")
    print(f"  Queue IDs:           {summary['queue_id_dist']}")
    print(f"  Set numbers:         {summary['set_number_dist']}")
    print(f"  Game length:         {summary['game_length']['avg_min']} min avg "
          f"({summary['game_length']['min_sec']:.0f}s ~ {summary['game_length']['max_sec']:.0f}s)")
    print(f"  Game versions:       {summary['game_versions']}")
    print(f"\n  Placement distribution:")
    for p, c in summary['placement_dist'].items():
        bar = "#" * (c // 5)
        print(f"    #{p}: {c:4d} {bar}")
    print(f"\n  Unique traits:       {summary['unique_traits']}")
    print(f"  Unique champions:    {summary['unique_champions']}")
    print(f"  Unique augments:     {summary['unique_augments']}")

    save_json(summary, "data_overview.json")
    return summary


# === Main ===
async def main():
    max_matches = TARGET_MATCHES
    skip_details = False

    for arg in sys.argv[1:]:
        if arg == "--max-matches" and len(sys.argv) > sys.argv.index(arg) + 1:
            max_matches = int(sys.argv[sys.argv.index(arg) + 1])
        if arg == "--skip-details":
            skip_details = True

    print("=" * 60)
    print("  TFT Challenger Match Data Fetcher")
    print(f"  Platform: {PLATFORM} | Regional: {REGIONAL}")
    print(f"  Time: {datetime.fromtimestamp(START_TIME, CST)} ~ {datetime.fromtimestamp(END_TIME, CST)}")
    print(f"  Target: {max_matches} matches")
    print("=" * 60)

    t0 = time.monotonic()

    # Step 1
    puuids = await step1_fetch_challengers()

    # Step 2
    match_ids = await step2_fetch_match_ids(puuids)

    if not match_ids:
        print("\n[ABORT] No match IDs found. Possible reasons:")
        print("  - No matches played in the time range")
        print("  - API rate limit hit")
        sys.exit(1)

    print(f"\n  Available match IDs: {len(match_ids)}")
    print(f"  Will fetch: {min(len(match_ids), max_matches)} matches")

    # Step 3
    if not skip_details:
        await step3_fetch_details(match_ids, max_matches)

    # Step 4
    step4_overview()

    elapsed = time.monotonic() - t0
    print(f"\n{'=' * 60}")
    print(f"  All done in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
