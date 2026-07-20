"""Generate retrieval_200.jsonl from real tft.db champion-trait mappings.

Run:  python scripts/generate_retrieval_dataset.py
Output: tests/eval/datasets/retrieval_200.jsonl
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tft.db"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "tests" / "eval" / "datasets" / "retrieval_200.jsonl"


def load_data() -> tuple[list[dict], list[dict]]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT ch.id, ch.name_zh, ch.name_en, ch.cost,
               GROUP_CONCAT(t.name_zh, '|') as traits_zh,
               GROUP_CONCAT(t.id, '|') as trait_ids
        FROM champions ch
        LEFT JOIN champion_traits ct ON ch.id = ct.champion_id
        LEFT JOIN traits t ON ct.trait_id = t.id
        GROUP BY ch.id
        ORDER BY ch.cost DESC, ch.name_zh
    """)
    champions = [dict(r) for r in c.fetchall()]
    for ch in champions:
        ch["traits_zh_list"] = ch["traits_zh"].split("|") if ch["traits_zh"] else []
        ch["trait_id_list"] = ch["trait_ids"].split("|") if ch["trait_ids"] else []

    c.execute("SELECT id, name_zh, name_en FROM traits ORDER BY name_zh")
    traits = [dict(r) for r in c.fetchall()]
    conn.close()
    return champions, traits


def by_cost(champions: list[dict], cost: int) -> list[dict]:
    return [ch for ch in champions if ch["cost"] == cost]


def first_trait(ch: dict) -> str:
    return ch["trait_id_list"][0] if ch["trait_id_list"] else ""


def first_trait_zh(ch: dict) -> str:
    return ch["traits_zh_list"][0] if ch["traits_zh_list"] else ""


# ---------------------------------------------------------------------------
# Query generators per category
# ---------------------------------------------------------------------------

def gen_cost5_main_carry(cost5: list[dict]) -> list[dict]:
    """40 queries featuring 5-cost champions as main carry."""
    records = []
    templates = [
        "S17 {name}主C出装推荐",
        "Set17 {trait}{name}最强装备",
        "{name}阵容运营思路 S17",
        "Set 17 {name}站位出装攻略",
        "S17 {name}怎么出装伤害最高",
        "{name}带什么装备 Set17",
        "S17太空 Gods {name}主C阵容",
        "Set17 {trait}{name}怎么搭配",
    ]
    for i, ch in enumerate(cost5):
        tpl = templates[i % len(templates)]
        q = tpl.format(name=ch["name_zh"], trait=first_trait_zh(ch))
        records.append({
            "query": q,
            "expected_champions": [ch["id"]],
            "expected_traits": ch["trait_id_list"],
            "category": "main_carry",
        })
    # Fill remaining to reach 40 by varying templates for first few champs
    extra_templates = [
        "S17 {name}天胡出装运营",
        "{trait}{name}阵容怎么站位",
        "Set17 {name}最强出装羁绊",
        "S17 {name}装备推荐优先级",
    ]
    while len(records) < 40:
        idx = len(records) % len(cost5)
        ch = cost5[idx]
        tpl = extra_templates[len(records) % len(extra_templates)]
        q = tpl.format(name=ch["name_zh"], trait=first_trait_zh(ch))
        records.append({
            "query": q,
            "expected_champions": [ch["id"]],
            "expected_traits": ch["trait_id_list"],
            "category": "main_carry",
        })
    return records[:40]


def gen_cost4_core(cost4: list[dict]) -> list[dict]:
    """30 queries for 4-cost core champions."""
    records = []
    templates = [
        "S17 {name}阵容搭配推荐",
        "Set17 {trait}{name}装备选择",
        "{name}适合什么阵容 S17",
        "S17 {name}羁绊效果出装",
        "Set 17 {trait}阵容{name}核心",
        "{name}怎么运营到三星 S17",
    ]
    for i, ch in enumerate(cost4):
        tpl = templates[i % len(templates)]
        q = tpl.format(name=ch["name_zh"], trait=first_trait_zh(ch))
        records.append({
            "query": q,
            "expected_champions": [ch["id"]],
            "expected_traits": ch["trait_id_list"],
            "category": "team_comp",
        })
    while len(records) < 30:
        idx = len(records) % len(cost4)
        ch = cost4[idx]
        tpl = templates[len(records) % len(templates)]
        q = tpl.format(name=ch["name_zh"], trait=first_trait_zh(ch))
        records.append({
            "query": q,
            "expected_champions": [ch["id"]],
            "expected_traits": ch["trait_id_list"],
            "category": "team_comp",
        })
    return records[:30]


def gen_cost32_main_carry(cost3: list[dict], cost2: list[dict]) -> list[dict]:
    """50 queries for 3-cost and 2-cost main carries."""
    records = []
    all_champs = cost3 + cost2
    templates = [
        "S17 {name}出装推荐",
        "Set17 {trait}{name}装备搭配",
        "{name}主C阵容怎么配 S17",
        "S17 {name}带什么装备最强",
        "Set 17 {name}站位和出装",
        "{trait}{name}阵容运营 S17",
        "S17 {name}装备优先级推荐",
        "{name}适合带什么羁绊 S17",
    ]
    for i, ch in enumerate(all_champs):
        tpl = templates[i % len(templates)]
        q = tpl.format(name=ch["name_zh"], trait=first_trait_zh(ch))
        records.append({
            "query": q,
            "expected_champions": [ch["id"]],
            "expected_traits": ch["trait_id_list"],
            "category": "itemization",
        })
    while len(records) < 50:
        idx = len(records) % len(all_champs)
        ch = all_champs[idx]
        tpl = templates[len(records) % len(templates)]
        q = tpl.format(name=ch["name_zh"], trait=first_trait_zh(ch))
        records.append({
            "query": q,
            "expected_champions": [ch["id"]],
            "expected_traits": ch["trait_id_list"],
            "category": "itemization",
        })
    return records[:50]


def gen_cost1_positioning_meta(cost1: list[dict], champions: list[dict]) -> list[dict]:
    """40 queries for 1-cost, positioning, economy, and version meta."""
    records = []

    # 1-cost specific queries (20)
    templates = [
        "S17 {name}过渡出装推荐",
        "Set17 {trait}{name}前期怎么过渡",
        "{name}前期打工装备 S17",
        "S17 {name}怎么站位前期",
        "Set 17 一费{name}装备推荐",
    ]
    for i, ch in enumerate(cost1):
        tpl = templates[i % len(templates)]
        q = tpl.format(name=ch["name_zh"], trait=first_trait_zh(ch))
        records.append({
            "query": q,
            "expected_champions": [ch["id"]],
            "expected_traits": ch["trait_id_list"],
            "category": "positioning",
        })
    while len(records) < 20:
        idx = len(records) % len(cost1)
        ch = cost1[idx]
        tpl = templates[len(records) % len(templates)]
        q = tpl.format(name=ch["name_zh"], trait=first_trait_zh(ch))
        records.append({
            "query": q,
            "expected_champions": [ch["id"]],
            "expected_traits": ch["trait_id_list"],
            "category": "positioning",
        })

    # Version meta / general queries (20)
    meta_queries = [
        {"query": "当前版本 T0 阵容推荐", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "S17 版本强势阵容排名", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "Set17 上分最快阵容", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "S17 太空 Gods 版本更新强势羁绊", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "S17 前期过渡阵容推荐", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "Set17 后期决赛圈站位技巧", "expected_champions": [], "expected_traits": [], "category": "positioning"},
        {"query": "S17 经济运营节奏怎么把握", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "Set 17 连胜连败运营思路", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "S17 什么阵容克制法师阵容", "expected_champions": [], "expected_traits": ["TFT17_APTrait"], "category": "version_meta"},
        {"query": "S17 重装战士阵容怎么打刺客", "expected_champions": [], "expected_traits": ["TFT17_ShieldTank", "TFT17_AssassinTrait"], "category": "version_meta"},
        {"query": "Set17 狙神阵容站位怎么摆", "expected_champions": [], "expected_traits": ["TFT17_RangedTrait"], "category": "positioning"},
        {"query": "S17 狂战士阵容出装站位", "expected_champions": [], "expected_traits": ["TFT17_MeleeTrait"], "category": "positioning"},
        {"query": "S17 太空律动羁绊效果是什么", "expected_champions": [], "expected_traits": ["TFT17_SpaceGroove"], "category": "version_meta"},
        {"query": "Set17 观星者羁绊怎么触发", "expected_champions": [], "expected_traits": ["TFT17_Stargazer_Wolf"], "category": "version_meta"},
        {"query": "S17 暗星羁绊效果加成机制", "expected_champions": [], "expected_traits": ["TFT17_DarkStar"], "category": "version_meta"},
        {"query": "S17 什么时候升人口什么时候D牌", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "Set 17 强化符文优先级排名", "expected_champions": [], "expected_traits": [], "category": "version_meta"},
        {"query": "S17 决赛圈对位站位调整", "expected_champions": [], "expected_traits": [], "category": "positioning"},
        {"query": "S17 木灵族羁绊效果详解", "expected_champions": [], "expected_traits": ["TFT17_Astronaut"], "category": "version_meta"},
        {"query": "Set17 幻灵战队羁绊怎么玩", "expected_champions": [], "expected_traits": ["TFT17_AnimaSquad"], "category": "version_meta"},
    ]
    records.extend(meta_queries)
    return records[:40]


def gen_trait_combo(champions: list[dict], traits: list[dict]) -> list[dict]:
    """40 queries for trait combinations, counters, and synergies."""
    records = []

    # Build trait→champions index
    trait_to_champs: dict[str, list[dict]] = {}
    for ch in champions:
        for tid, tzh in zip(ch["trait_id_list"], ch["traits_zh_list"]):
            trait_to_champs.setdefault(tid, []).append(ch)

    # Trait combo queries — pick real trait pairs that share champions or complement
    # We generate queries referencing specific trait+champion combos that exist in the DB
    combo_specs = []
    for ch in champions:
        if len(ch["trait_id_list"]) >= 2:
            combo_specs.append({
                "trait_zh": ch["traits_zh_list"][0],
                "trait_id": ch["trait_id_list"][0],
                "trait2_zh": ch["traits_zh_list"][1],
                "trait2_id": ch["trait_id_list"][1],
                "name_zh": ch["name_zh"],
                "champ_id": ch["id"],
            })
        if len(combo_specs) >= 25:
            break

    combo_templates = [
        "S17 {trait_zh}{name_zh}搭配{trait2_zh}阵容",
        "Set17 {trait_zh}加{trait2_zh}双羁绊{name_zh}",
        "S17 {trait_zh}和{trait2_zh}怎么配合{name_zh}",
        "{name_zh}的{trait_zh}和{trait2_zh}羁绊联动",
        "Set 17 {trait_zh}{trait2_zh}阵容{name_zh}核心",
    ]
    for i, spec in enumerate(combo_specs):
        tpl = combo_templates[i % len(combo_templates)]
        q = tpl.format(**spec)
        records.append({
            "query": q,
            "expected_champions": [spec["champ_id"]],
            "expected_traits": [spec["trait_id"], spec["trait2_id"]],
            "category": "team_comp",
        })

    # Synergy / counter queries using real traits
    synergy_traits = [
        ("TFT17_DarkStar", "暗星"),
        ("TFT17_AnimaSquad", "幻灵战队"),
        ("TFT17_Mecha", "霸天机甲"),
        ("TFT17_DRX", "新星特攻队"),
        ("TFT17_PsyOps", "灵能特工"),
        ("TFT17_Timebreaker", "未来战士"),
        ("TFT17_SpaceGroove", "太空律动"),
        ("TFT17_Astronaut", "木灵族"),
        ("TFT17_Stargazer_Wolf", "观星者"),
        ("TFT17_ResistTank", "堡垒卫士"),
        ("TFT17_ShieldTank", "重装战士"),
        ("TFT17_HPTank", "斗士"),
        ("TFT17_ASTrait", "挑战者"),
        ("TFT17_MeleeTrait", "狂战士"),
        ("TFT17_RangedTrait", "狙神"),
    ]
    synergy_templates = [
        "S17 {zh}阵容全部棋子推荐",
        "Set17 {zh}羁绊搭配什么阵容",
        "S17 {zh}羁绊核心英雄有哪些",
        "Set 17 {zh}阵容怎么运营",
        "S17 {zh}羁绊克制什么阵容",
    ]
    idx = 0
    while len(records) < 40:
        tid, zh = synergy_traits[idx % len(synergy_traits)]
        tpl = synergy_templates[idx % len(synergy_templates)]
        q = tpl.format(zh=zh)
        champ_ids = [c["id"] for c in trait_to_champs.get(tid, [])]
        records.append({
            "query": q,
            "expected_champions": champ_ids[:5],
            "expected_traits": [tid],
            "category": "team_comp",
        })
        idx += 1

    return records[:40]


def main():
    champions, traits = load_data()

    cost5 = by_cost(champions, 5)
    cost4 = by_cost(champions, 4)
    cost3 = by_cost(champions, 3)
    cost2 = by_cost(champions, 2)
    cost1 = by_cost(champions, 1)

    print(f"Champions by cost: 5费={len(cost5)} 4费={len(cost4)} 3费={len(cost3)} 2费={len(cost2)} 1费={len(cost1)}")

    records: list[dict] = []
    records.extend(gen_cost5_main_carry(cost5))
    records.extend(gen_cost4_core(cost4))
    records.extend(gen_cost32_main_carry(cost3, cost2))
    records.extend(gen_cost1_positioning_meta(cost1, champions))
    records.extend(gen_trait_combo(champions, traits))

    assert len(records) == 200, f"Expected 200 records, got {len(records)}"

    # Verify all champion_ids exist in DB
    valid_ids = {ch["id"] for ch in champions}
    valid_tids = {t["id"] for t in traits}
    for rec in records:
        for cid in rec["expected_champions"]:
            assert cid in valid_ids, f"Unknown champion_id: {cid} in query: {rec['query']}"
        for tid in rec["expected_traits"]:
            assert tid in valid_tids, f"Unknown trait_id: {tid} in query: {rec['query']}"

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Category distribution
    from collections import Counter
    cat_counts = Counter(r["category"] for r in records)
    print(f"Generated {len(records)} records → {OUTPUT_PATH}")
    for cat, cnt in cat_counts.most_common():
        print(f"  {cat}: {cnt}")


if __name__ == "__main__":
    main()
