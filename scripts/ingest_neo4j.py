"""Ingest TFT champion-trait-item graph into Neo4j.

Reads data/tft.db and populates Neo4j with:
- (:Champion {id, name_zh, name_en, cost})
- (:Trait {id, name_zh})
- (:Item {id, name_zh})
- (:Champion)-[:HAS_TRAIT]->(:Trait)
- (:Champion)-[:RECOMMENDS {delta_rank}]->(:Item)

Usage:
    python scripts/ingest_neo4j.py [--db data/tft.db]

Prerequisites:
    - Neo4j 5 running on bolt://localhost:7687
    - Default credentials: neo4j / tft_neo4j
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def verify_graph(store) -> None:
    """Run verification queries to confirm data was ingested correctly."""
    print("\n── 验证图数据 ──")

    # Count nodes
    champions = store.run_cypher("MATCH (c:Champion) RETURN count(c) AS n")
    traits = store.run_cypher("MATCH (t:Trait) RETURN count(t) AS n")
    items = store.run_cypher("MATCH (i:Item) RETURN count(i) AS n")
    rels = store.run_cypher("MATCH ()-[r]->() RETURN count(r) AS n")

    print(f"  Champion 节点: {champions[0]['n']}")
    print(f"  Trait 节点:    {traits[0]['n']}")
    print(f"  Item 节点:     {items[0]['n']}")
    print(f"  关系总数:      {rels[0]['n']}")

    # Test two-hop synergy query
    print("\n── 测试两跳协同查询（亚索）──")
    synergies = store.run_cypher(
        "MATCH (c:Champion {name_zh: '亚索'})-[:HAS_TRAIT]->(t:Trait)"
        "<-[:HAS_TRAIT]-(other:Champion) "
        "WHERE other <> c "
        "WITH other, collect(t.name_zh) AS shared "
        "RETURN other.name_zh AS champion, shared AS shared_traits, size(shared) AS count "
        "ORDER BY count DESC LIMIT 5"
    )
    if synergies:
        for s in synergies:
            print(f"  {s['champion']}: 共享 {s['shared_traits']} ({s['count']}个)")
    else:
        print("  （无结果 — 可能亚索节点不存在）")

    # Test trait members query
    print("\n── 测试羁绊成员查询 ──")
    trait_sample = store.run_cypher(
        "MATCH (t:Trait)<-[:HAS_TRAIT]-(c:Champion) "
        "WITH t, count(c) AS members "
        "ORDER BY members DESC LIMIT 3 "
        "RETURN t.name_zh AS trait, members"
    )
    for t in trait_sample:
        print(f"  {t['trait']}: {t['members']} 个英雄")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest TFT graph into Neo4j")
    parser.add_argument("--db", default="data/tft.db", help="Path to tft.db")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j Bolt URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="tft_neo4j", help="Neo4j password")
    parser.add_argument("--verify", action="store_true", default=True, help="Run verification queries")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)

    from api.services.rag.graph_store import GraphStore

    print(f"[1/3] 连接 Neo4j ({args.uri})...")
    store = GraphStore(uri=args.uri, user=args.user, password=args.password)
    try:
        store.connect()
    except Exception as exc:
        print(f"错误: 无法连接 Neo4j: {exc}")
        print("请确认 Neo4j 容器已启动: docker compose up -d neo4j")
        sys.exit(1)

    if not store.is_healthy():
        print("错误: Neo4j 连接不健康，请检查服务状态")
        sys.exit(1)

    print(f"[2/3] 从 {db_path} 导入图数据...")
    start = time.time()
    count = store.build_from_sqlite(str(db_path))
    elapsed = time.time() - start
    print(f"  导入完成: {count} 个实体/关系，耗时 {elapsed:.1f}s")

    if args.verify:
        print(f"[3/3] 验证...")
        verify_graph(store)
    else:
        print("[3/3] 跳过验证")

    store.close()
    print("\n完成！Neo4j 图数据已就绪。")


if __name__ == "__main__":
    main()
