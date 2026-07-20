"""
Data Dragon → SQLite Import Script
====================================
将 Data Dragon JSON 静态数据导入统一 SQLite 数据库。

导入内容:
  champions   — 英雄（Set17, cost>0）
  items       — 装备（Set17）
  traits      — 羁绊（Set17）
  augments    — 强化（Set17）
  aliases     — 英雄别名字典

数据源:
  asset/data/zh_CN/*.json + asset/data/en_US/*.json
  asset/data/cleaned/units.csv (用于推导 champion_traits)

用法:
  uv run python data_collection/scripts/import_data_dragon.py

依赖: 无额外依赖（纯标准库）
"""

import json
import sqlite3
import csv
import os
import re
from pathlib import Path
from collections import defaultdict

# === Paths ===
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # tft-agent-set17/
ASSET_DIR = PROJECT_ROOT / "asset"
DATA_ZH = ASSET_DIR / "data" / "zh_CN"
DATA_EN = ASSET_DIR / "data" / "en_US"
IMG_DIR = ASSET_DIR / "img"
CLEANED_DIR = PROJECT_ROOT / "data_collection" / "data" / "cleaned"
DB_PATH = PROJECT_ROOT / "data" / "tft.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_set17(key: str, entry: dict) -> bool:
    """Check if an entry belongs to Set 17."""
    entry_id = entry.get("id", "")
    return "TFT17" in key or "TFT17" in entry_id or "Set17" in key


# ============================================================
# Schema
# ============================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS champions (
    id          TEXT PRIMARY KEY,
    name_zh     TEXT NOT NULL,
    name_en     TEXT,
    tier        INTEGER,
    cost        INTEGER,
    icon_path   TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    name_zh     TEXT NOT NULL,
    name_en     TEXT,
    icon_path   TEXT
);

CREATE TABLE IF NOT EXISTS traits (
    id          TEXT PRIMARY KEY,
    name_zh     TEXT NOT NULL,
    name_en     TEXT,
    icon_path   TEXT
);

CREATE TABLE IF NOT EXISTS augments (
    id              TEXT PRIMARY KEY,
    name_zh         TEXT NOT NULL,
    name_en         TEXT,
    description_zh  TEXT,
    description_en  TEXT,
    icon_path       TEXT
);

CREATE TABLE IF NOT EXISTS champion_traits (
    champion_id TEXT NOT NULL,
    trait_id    TEXT NOT NULL,
    PRIMARY KEY (champion_id, trait_id),
    FOREIGN KEY (champion_id) REFERENCES champions(id),
    FOREIGN KEY (trait_id) REFERENCES traits(id)
);

CREATE TABLE IF NOT EXISTS aliases (
    alias       TEXT PRIMARY KEY,
    champion_id TEXT NOT NULL,
    FOREIGN KEY (champion_id) REFERENCES champions(id)
);

CREATE TABLE IF NOT EXISTS item_stats (
    item_id     TEXT NOT NULL,
    champion_id TEXT,
    delta_rank  REAL,
    sample_size INTEGER,
    PRIMARY KEY (item_id, champion_id)
);

CREATE INDEX IF NOT EXISTS idx_aliases_champion ON aliases(champion_id);
"""


def create_tables(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)
    conn.commit()


# ============================================================
# Import Champions
# ============================================================
def import_champions(conn: sqlite3.Connection):
    zh_data = load_json(DATA_ZH / "champion.json")["data"]
    en_data = load_json(DATA_EN / "champion.json")["data"]

    # Build en lookup by id
    en_lookup = {}
    for entry in en_data.values():
        en_lookup[entry["id"]] = entry.get("name", "")

    count = 0
    for entry in zh_data.values():
        entry_id = entry["id"]
        cost = entry.get("cost", 0)

        # Filter: Set17 only, real champions (cost > 0)
        if not entry_id.startswith("TFT17"):
            continue
        if cost == 0:
            continue
        # Skip clone/fake/enemy units
        if any(x in entry_id for x in ["_TraitClone", "_FakeUnit", "Enemy_"]):
            continue

        name_zh = entry.get("name", "")
        name_en = en_lookup.get(entry_id, "")
        tier = entry.get("tier", 0)
        icon = entry.get("image", {}).get("full", "")
        icon_path = f"champion/{icon}" if icon else None

        conn.execute(
            "INSERT OR REPLACE INTO champions (id, name_zh, name_en, tier, cost, icon_path) VALUES (?, ?, ?, ?, ?, ?)",
            (entry_id, name_zh, name_en, tier, cost, icon_path),
        )
        count += 1

    conn.commit()
    print(f"  Champions: {count}")


# ============================================================
# Import Items
# ============================================================
def import_items(conn: sqlite3.Connection):
    zh_data = load_json(DATA_ZH / "item.json")["data"]
    en_data = load_json(DATA_EN / "item.json")["data"]

    en_lookup = {}
    for entry in en_data.values():
        en_lookup[entry["id"]] = entry.get("name", "")

    count = 0
    for entry in zh_data.values():
        entry_id = entry["id"]

        # Filter: Set17 items + base/completed items (TFT_Item_*)
        is_set17_item = entry_id.startswith("TFT17") or entry_id.startswith("TFT_Item_")
        if not is_set17_item:
            continue

        name_zh = entry.get("name", "")
        name_en = en_lookup.get(entry_id, "")
        icon = entry.get("image", {}).get("full", "")
        icon_path = f"items/{icon}" if icon else None

        conn.execute(
            "INSERT OR REPLACE INTO items (id, name_zh, name_en, icon_path) VALUES (?, ?, ?, ?)",
            (entry_id, name_zh, name_en, icon_path),
        )
        count += 1

    conn.commit()
    print(f"  Items: {count}")


# ============================================================
# Import Traits
# ============================================================
def import_traits(conn: sqlite3.Connection):
    zh_data = load_json(DATA_ZH / "trait.json")["data"]
    en_data = load_json(DATA_EN / "trait.json")["data"]

    en_lookup = {}
    for entry in en_data.values():
        en_lookup[entry["id"]] = entry.get("name", "")

    count = 0
    for entry in zh_data.values():
        entry_id = entry["id"]
        if not entry_id.startswith("TFT17"):
            continue

        name_zh = entry.get("name", "")
        name_en = en_lookup.get(entry_id, "")
        icon = entry.get("image", {}).get("full", "")
        icon_path = f"traits/{icon}" if icon else None

        conn.execute(
            "INSERT OR REPLACE INTO traits (id, name_zh, name_en, icon_path) VALUES (?, ?, ?, ?)",
            (entry_id, name_zh, name_en, icon_path),
        )
        count += 1

    conn.commit()
    print(f"  Traits: {count}")


# ============================================================
# Import Augments
# ============================================================
def import_augments(conn: sqlite3.Connection):
    zh_data = load_json(DATA_ZH / "augments.json")["data"]
    en_data = load_json(DATA_EN / "augments.json")["data"]

    en_lookup = {}
    for entry in en_data.values():
        en_lookup[entry["id"]] = {
            "name": entry.get("name", ""),
            "desc": entry.get("description", ""),
        }

    count = 0
    for entry in zh_data.values():
        entry_id = entry["id"]
        if not entry_id.startswith("TFT17"):
            continue

        name_zh = entry.get("name", "")
        desc_zh = entry.get("description", "")
        en_info = en_lookup.get(entry_id, {})
        name_en = en_info.get("name", "")
        desc_en = en_info.get("desc", "")
        icon = entry.get("image", {}).get("full", "")
        icon_path = f"augment/{icon}" if icon else None

        conn.execute(
            "INSERT OR REPLACE INTO augments (id, name_zh, name_en, description_zh, description_en, icon_path) VALUES (?, ?, ?, ?, ?, ?)",
            (entry_id, name_zh, name_en, desc_zh, desc_en, icon_path),
        )
        count += 1

    conn.commit()
    print(f"  Augments: {count}")


# ============================================================
# Import Champion-Trait mapping from CDragon
# ============================================================
CDRAGON_URL = "https://raw.communitydragon.org/latest/cdragon/tft/zh_cn.json"


def import_champion_traits(conn: sqlite3.Connection):
    """
    Import champion→trait mapping from Community Dragon (CDragon).

    CDragon provides authoritative per-champion trait lists, unlike the
    Riot Data Dragon champion.json which lacks trait fields.

    Falls back to empty if the network request fails.
    """
    import urllib.request

    try:
        req = urllib.request.Request(CDRAGON_URL, headers={"User-Agent": "tft-agent/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] CDragon fetch failed: {e}")
        return

    # Find Set 17
    set17 = None
    for s in data.get("setData", []):
        if s.get("mutator") == "TFTSet17":
            set17 = s
            break
    if set17 is None:
        print("  [WARN] Set 17 not found in CDragon data")
        return

    # Build trait name_zh → id lookup from DB
    trait_lookup = dict(conn.execute("SELECT name_zh, id FROM traits").fetchall())
    db_champions = set(r[0] for r in conn.execute("SELECT id FROM champions").fetchall())

    count = 0
    skipped = 0
    for champ in set17.get("champions", []):
        api_name = champ.get("apiName", "")
        traits = champ.get("traits", [])
        cost = champ.get("cost", 0)

        if not api_name.startswith("TFT17") or cost == 0 or not traits:
            continue
        if api_name not in db_champions:
            continue

        for trait_name in traits:
            trait_id = trait_lookup.get(trait_name)
            if trait_id is None:
                skipped += 1
                continue
            conn.execute(
                "INSERT OR IGNORE INTO champion_traits (champion_id, trait_id) VALUES (?, ?)",
                (api_name, trait_id),
            )
            count += 1

    conn.commit()
    msg = f"  Champion-Trait mappings: {count} (CDragon)"
    if skipped:
        msg += f", {skipped} skipped (trait not in DB)"
    print(msg)


# ============================================================
# Build Alias Dictionary
# ============================================================
def build_aliases(conn: sqlite3.Connection):
    """Build champion alias dictionary: zh name, en name, pinyin variants, common nicknames."""
    rows = conn.execute("SELECT id, name_zh, name_en FROM champions").fetchall()

    count = 0
    for champ_id, name_zh, name_en in rows:
        aliases = set()

        # Official Chinese name
        if name_zh:
            aliases.add(name_zh)

        # Official English name
        if name_en:
            aliases.add(name_en)
            aliases.add(name_en.lower())

        # Extract short ID (e.g. TFT17_Briar → Briar)
        short = champ_id.replace("TFT17_", "")
        aliases.add(short)
        aliases.add(short.lower())

        for alias in aliases:
            conn.execute(
                "INSERT OR IGNORE INTO aliases (alias, champion_id) VALUES (?, ?)",
                (alias, champ_id),
            )
            count += 1

    conn.commit()
    print(f"  Aliases: {count}")


# ============================================================
# Summary
# ============================================================
def print_summary(conn: sqlite3.Connection):
    tables = ["champions", "items", "traits", "augments", "champion_traits", "aliases", "item_stats"]
    print(f"\n{'='*50}")
    print(f"  Database: {DB_PATH}")
    print(f"  Size: {DB_PATH.stat().st_size / 1024:.1f} KB")
    print(f"{'='*50}")
    for t in tables:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:20s}: {n:>6d} rows")

    # Sample champions
    print(f"\n  Sample champions (cost 4-5):")
    for row in conn.execute("SELECT id, name_zh, name_en, cost FROM champions WHERE cost >= 4 ORDER BY cost DESC, name_zh LIMIT 10"):
        print(f"    {row[0]:30s} {row[1]:12s} {row[2]:20s} cost={row[3]}")

    # Sample champion-traits
    print(f"\n  Sample champion-trait mappings:")
    for row in conn.execute("""
        SELECT c.name_zh, t.name_zh
        FROM champion_traits ct
        JOIN champions c ON c.id = ct.champion_id
        JOIN traits t ON t.id = ct.trait_id
        ORDER BY c.name_zh
        LIMIT 10
    """):
        print(f"    {row[0]:12s} → {row[1]}")


# ============================================================
# Main
# ============================================================
def main():
    print("="*50)
    print("  Data Dragon → SQLite Import")
    print(f"  Source: {DATA_ZH}")
    print(f"  Target: {DB_PATH}")
    print("="*50)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    print("\nCreating tables ...")
    create_tables(conn)

    print("\nImporting data ...")
    import_champions(conn)
    import_items(conn)
    import_traits(conn)
    import_augments(conn)

    print("\nImporting champion-trait mappings from CDragon ...")
    conn.execute("DELETE FROM champion_traits")
    import_champion_traits(conn)

    print("\nBuilding alias dictionary ...")
    build_aliases(conn)

    print_summary(conn)

    conn.close()
    print(f"\nDone!")


if __name__ == "__main__":
    main()
