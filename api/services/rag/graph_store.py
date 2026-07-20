"""Neo4j graph store — champion / item / trait relationship queries."""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import for neo4j driver
# ---------------------------------------------------------------------------
_neo4j_mod: Any = None


def _get_neo4j() -> Any:
    global _neo4j_mod
    if _neo4j_mod is None:
        try:
            import neo4j as _n

            _neo4j_mod = _n
        except ImportError as exc:
            raise ImportError(
                "neo4j is required for GraphStore. "
                "Install it with: pip install neo4j"
            ) from exc
    return _neo4j_mod


class GraphStore:
    """Neo4j-backed graph store for TFT domain relationships.

    Schema (nodes → relationships):
    * ``(:Champion)-[:HAS_TRAIT]->(:Trait)``
    * ``(:Champion)-[:RECOMMENDS]->(:Item)``
    * ``(:Item)-[:BELONGS_TO]->(:Trait)``
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "tft_neo4j",
    ) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: Any = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> None:
        neo4j = _get_neo4j()
        self._driver = neo4j.GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        logger.info("Connected to Neo4j at %s", self._uri)

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def is_healthy(self) -> bool:
        if self._driver is None:
            return False
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Generic Cypher execution
    # ------------------------------------------------------------------
    def run_cypher(self, cypher: str, params: dict | None = None) -> list[dict]:
        """Execute a read-only Cypher query and return records as dicts."""
        if self._driver is None:
            raise RuntimeError("GraphStore not connected — call connect() first")

        with self._driver.session() as session:
            result = session.run(cypher, parameters=params or {})
            return [record.data() for record in result]

    # ------------------------------------------------------------------
    # Domain-specific queries (two-hop reasoning)
    # ------------------------------------------------------------------
    def get_champion_synergies(self, champion_name: str) -> list[dict]:
        """Two-hop query: champion → traits → other champions sharing traits.

        Returns a list of dicts with keys: ``champion``, ``shared_traits``,
        ``count``.
        """
        cypher = """
        MATCH (c:Champion {name_zh: $name})-[:HAS_TRAIT]->(t:Trait)
              <-[:HAS_TRAIT]-(other:Champion)
        WHERE other <> c
        WITH other, collect(t.name_zh) AS shared
        RETURN other.name_zh AS champion,
               shared        AS shared_traits,
               size(shared)  AS count
        ORDER BY count DESC
        LIMIT 10
        """
        return self.run_cypher(cypher, {"name": champion_name})

    def get_champion_items(self, champion_name: str, limit: int = 10) -> list[dict]:
        """Champion → recommended items."""
        cypher = """
        MATCH (c:Champion {name_zh: $name})-[r:RECOMMENDS]->(i:Item)
        RETURN i.name_zh AS item, r.delta_rank AS delta_rank
        ORDER BY r.delta_rank ASC
        LIMIT $limit
        """
        return self.run_cypher(cypher, {"name": champion_name, "limit": limit})

    def get_trait_comps(self, trait_name: str) -> list[dict]:
        """Trait → champions → popular comps anchored on that trait."""
        cypher = """
        MATCH (t:Trait {name_zh: $name})<-[:HAS_TRAIT]-(c:Champion)
        RETURN c.name_zh AS champion, c.cost AS cost
        ORDER BY cost DESC
        """
        return self.run_cypher(cypher, {"name": trait_name})

    # ------------------------------------------------------------------
    # Ingestion helpers (called during data pipeline)
    # ------------------------------------------------------------------
    def build_from_sqlite(self, sqlite_path: str) -> int:
        """Populate the graph from the existing SQLite tft.db.

        Creates Champion, Trait, Item nodes and relationships.
        Returns the number of relationships created.
        """
        import sqlite3

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        count = 0
        with self._driver.session() as session:
            # Create champion nodes
            for row in conn.execute("SELECT id, name_zh, name_en, cost FROM champions"):
                session.run(
                    "MERGE (c:Champion {id: $id}) "
                    "SET c.name_zh = $name_zh, c.name_en = $name_en, c.cost = $cost",
                    parameters=dict(row),
                )
                count += 1

            # Create trait nodes
            for row in conn.execute("SELECT id, name_zh FROM traits"):
                session.run(
                    "MERGE (t:Trait {id: $id}) SET t.name_zh = $name_zh",
                    parameters=dict(row),
                )
                count += 1

            # Create item nodes
            for row in conn.execute("SELECT id, name_zh FROM items"):
                session.run(
                    "MERGE (i:Item {id: $id}) SET i.name_zh = $name_zh",
                    parameters=dict(row),
                )
                count += 1

            # Champion → Trait relationships
            for row in conn.execute(
                "SELECT champion_id, trait_id FROM champion_traits"
            ):
                session.run(
                    "MATCH (c:Champion {id: $cid}), (t:Trait {id: $tid}) "
                    "MERGE (c)-[:HAS_TRAIT]->(t)",
                    parameters={"cid": row["champion_id"], "tid": row["trait_id"]},
                )
                count += 1

            # Champion → Item relationships (from item_stats, top 10 per champ)
            for row in conn.execute(
                "SELECT champion_id, item_id, delta_rank FROM item_stats "
                "ORDER BY champion_id, delta_rank ASC"
            ):
                session.run(
                    "MATCH (c:Champion {id: $cid}), (i:Item {id: $iid}) "
                    "MERGE (c)-[r:RECOMMENDS]->(i) "
                    "SET r.delta_rank = $delta",
                    parameters={
                        "cid": row["champion_id"],
                        "iid": row["item_id"],
                        "delta": row["delta_rank"],
                    },
                )
                count += 1

        conn.close()
        logger.info("Graph build complete: %d entities/relationships", count)
        return count
