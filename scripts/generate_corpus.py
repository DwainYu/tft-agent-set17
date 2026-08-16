"""Generate a real, multi-section TFT strategy corpus from data/tft.db.

The RAG pipeline needs genuine *documents* to parse and chunk — not single
sentences templated out of a database.  This script turns the mined data in
``data/tft.db`` (compositions, member roles, item win-rate deltas, traits)
into well-structured Markdown strategy guides that read like real player
guides.  The downstream ingestion pipeline then parses, chunks, embeds and
stores them.

Corpus layout (under ``--out``, default ``data/corpus``)::

    comps/   one guide per mined composition (anchor, members, items, play)
    traits/  one guide per trait (members + activation hints)
    meta/    a single patch-level tier overview of the strongest comps

Usage::

    python scripts/generate_corpus.py [--db data/tft.db] [--out data/corpus]

The generator is deterministic and idempotent: re-running simply overwrites
the produced files.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_patch(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT patch FROM comps WHERE patch IS NOT NULL LIMIT 1").fetchone()
    return row["patch"] if row else "当前版本"


def _champion_name(conn: sqlite3.Connection, champion_id: str) -> str:
    row = conn.execute(
        "SELECT name_zh FROM champions WHERE id = ?", (champion_id,)
    ).fetchone()
    return row["name_zh"] if row else champion_id


def _anchor_items(conn: sqlite3.Connection, champion_id: str, limit: int = 6) -> list[dict]:
    rows = conn.execute(
        """
        SELECT i.name_zh AS item, s.delta_rank, s.sample_size
        FROM item_stats s
        JOIN items i ON s.item_id = i.id
        WHERE s.champion_id = ? AND i.name_zh != ''
          AND i.name_zh NOT LIKE '%纹章%'
        ORDER BY s.delta_rank ASC
        LIMIT ?
        """,
        (champion_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _placement_comment(avg_placement: float) -> str:
    if avg_placement <= 2.5:
        return "数据表现顶尖，是当前版本的强势上分阵容。"
    if avg_placement <= 3.5:
        return "数据表现优秀，稳定吃分，适合大多数对局。"
    if avg_placement <= 4.5:
        return "数据表现中规中矩，需要较好的运营节奏才能吃分。"
    return "数据表现偏弱，更适合作为特定局势下的偏门选择。"


# ---------------------------------------------------------------------------
# Comp guides
# ---------------------------------------------------------------------------

def build_comp_guide(conn: sqlite3.Connection, comp: sqlite3.Row, patch: str) -> str:
    anchor_id = comp["anchor_id"]
    anchor = _champion_name(conn, anchor_id)
    try:
        top_traits = json.loads(comp["top_traits"]) if comp["top_traits"] else []
    except (json.JSONDecodeError, TypeError):
        top_traits = []

    members = conn.execute(
        """
        SELECT ch.name_zh AS name, cc.role, cc.avg_stars, cc.pick_rate, ch.cost
        FROM comp_champions cc
        JOIN champions ch ON cc.champion_id = ch.id
        WHERE cc.comp_id = ?
        ORDER BY CASE cc.role WHEN '主C' THEN 0 WHEN '副C' THEN 1
                              WHEN '坦克' THEN 2 ELSE 3 END, ch.cost DESC
        """,
        (comp["id"],),
    ).fetchall()

    lines: list[str] = []
    lines.append(f"# {comp['name']}")
    lines.append("")
    lines.append(
        f"> 版本 {patch} ｜ 平均名次 {comp['avg_placement']:.2f} ｜ "
        f"样本 {comp['sample_size']} 场 ｜ 核心：{anchor}"
    )
    lines.append("")

    # 概览
    lines.append("## 阵容概览")
    lines.append("")
    lines.append(
        f"{comp['name']}是一套以 {anchor} 为核心搭建的阵容，"
        f"共由 {len(members)} 名英雄组成。{_placement_comment(comp['avg_placement'])}"
    )
    lines.append("")

    # 成员与定位
    lines.append("## 核心英雄与定位")
    lines.append("")
    for m in members:
        stars = f"平均 {m['avg_stars']:.1f} 星"
        pick = f"选取率 {int(round(m['pick_rate'] * 100))}%"
        lines.append(f"- **{m['name']}**（{m['cost']} 费，{m['role']}）：{stars}，{pick}。")
    lines.append("")

    # 羁绊
    if top_traits:
        lines.append("## 核心羁绊")
        lines.append("")
        lines.append(
            "这套阵容主要围绕以下羁绊构建：" + "、".join(f"「{t}」" for t in top_traits) + "。"
            "凑齐高激活等级是阵容强度的关键，优先保证核心羁绊的激活。"
        )
        lines.append("")

    # 装备
    items = _anchor_items(conn, anchor_id)
    lines.append(f"## 装备推荐（{anchor}）")
    lines.append("")
    if items:
        lines.append(
            f"根据对局数据统计，以下装备能显著提升 {anchor} 的表现"
            "（delta_rank 越低代表名次提升越明显）："
        )
        lines.append("")
        for it in items:
            lines.append(
                f"- **{it['item']}**：名次提升 {it['delta_rank']:.2f}，样本 {it['sample_size']} 场。"
            )
    else:
        lines.append("暂无足够样本的装备数据，优先合成常规输出/防装。")
    lines.append("")

    # 运营思路
    lines.append("## 运营思路")
    lines.append("")
    main_c = next((m for m in members if m["role"] == "主C"), None)
    if main_c and main_c["cost"] >= 4:
        lines.append(
            f"主C {main_c['name']} 为 {main_c['cost']} 费高费卡，前期应以保血量和攒经济为主，"
            "用低费卡过渡，升到 7~8 级后再集中搜卡凑齐核心阵容。"
        )
    else:
        lines.append(
            "核心卡费用不高，可以在 6~7 级时较早搜卡追质量，用连胜或连败经济快速成型。"
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Trait guides
# ---------------------------------------------------------------------------

def build_trait_guide(conn: sqlite3.Connection, trait: sqlite3.Row) -> str | None:
    members = conn.execute(
        """
        SELECT c.name_zh AS name, c.cost
        FROM champion_traits ct
        JOIN champions c ON ct.champion_id = c.id
        WHERE ct.trait_id = ?
        ORDER BY c.cost DESC
        """,
        (trait["id"],),
    ).fetchall()
    if not members:
        return None

    member_str = "、".join(f"{m['name']}({m['cost']}费)" for m in members)
    count = len(members)
    if count >= 6:
        hint = "该羁绊英雄池充足，较容易凑出高激活等级。"
    elif count <= 3:
        hint = "该羁绊英雄较少，通常需要转职纹章或特定条件才能达到高激活。"
    else:
        hint = "该羁绊英雄数量适中，需要根据来牌情况决定是否追高激活。"

    return (
        f"# {trait['name_zh']}羁绊攻略\n\n"
        f"## 羁绊成员\n\n"
        f"羁绊「{trait['name_zh']}」（{trait['name_en']}）共有 {count} 个英雄：{member_str}。\n\n"
        f"## 激活建议\n\n{hint}\n"
    )


# ---------------------------------------------------------------------------
# Meta overview
# ---------------------------------------------------------------------------

def build_meta_overview(conn: sqlite3.Connection, patch: str) -> str:
    comps = conn.execute(
        "SELECT name, anchor_id, avg_placement, sample_size FROM comps "
        "ORDER BY avg_placement ASC LIMIT 12"
    ).fetchall()
    lines = [
        f"# {patch} 版本阵容梯队总览",
        "",
        "## 强势阵容排行",
        "",
        "以下阵容按平均名次从低到高排列（名次越低越强），数据来自高段位对局挖掘：",
        "",
    ]
    for i, c in enumerate(comps, 1):
        anchor = _champion_name(conn, c["anchor_id"])
        lines.append(
            f"{i}. **{c['name']}**（核心 {anchor}）：平均名次 {c['avg_placement']:.2f}，"
            f"样本 {c['sample_size']} 场。"
        )
    lines.append("")
    lines.append("## 上分建议")
    lines.append("")
    lines.append(
        "优先选择平均名次靠前且来牌顺畅的阵容；前期根据发牌灵活过渡，"
        "中后期再确定最终阵容方向，避免无脑硬玩单一套路。"
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(db_path: str, out_dir: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    patch = _load_patch(conn)

    counts = {"comps": 0, "traits": 0, "meta": 0}

    # Comps
    comps_dir = out_dir / "comps"
    comps_dir.mkdir(parents=True, exist_ok=True)
    for comp in conn.execute("SELECT * FROM comps ORDER BY id"):
        anchor = _champion_name(conn, comp["anchor_id"])
        content = build_comp_guide(conn, comp, patch)
        (comps_dir / f"{anchor}_阵容攻略.md").write_text(content, encoding="utf-8")
        counts["comps"] += 1

    # Traits
    traits_dir = out_dir / "traits"
    traits_dir.mkdir(parents=True, exist_ok=True)
    for trait in conn.execute("SELECT * FROM traits ORDER BY id"):
        content = build_trait_guide(conn, trait)
        if content:
            (traits_dir / f"{trait['name_zh']}_羁绊攻略.md").write_text(
                content, encoding="utf-8"
            )
            counts["traits"] += 1

    # Meta overview
    meta_dir = out_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / f"{patch}_版本阵容梯队.md").write_text(
        build_meta_overview(conn, patch), encoding="utf-8"
    )
    counts["meta"] = 1

    conn.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TFT strategy corpus")
    parser.add_argument("--db", default="data/tft.db")
    parser.add_argument("--out", default="data/corpus")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"错误：数据库不存在 {db_path}")
        sys.exit(1)

    out_dir = Path(args.out)
    counts = generate(str(db_path), out_dir)
    total = sum(counts.values())
    print(f"语料已生成到 {out_dir}/")
    print(f"  阵容攻略: {counts['comps']} 篇")
    print(f"  羁绊攻略: {counts['traits']} 篇")
    print(f"  版本总览: {counts['meta']} 篇")
    print(f"共 {total} 篇文档，可供 ingestion 管线解析与切分。")


if __name__ == "__main__":
    main()
