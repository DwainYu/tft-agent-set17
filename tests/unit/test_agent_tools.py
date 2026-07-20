"""Unit tests for api.agent.tools.ToolRegistry."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_db(tmp_path: Path) -> sqlite3.Connection:
    """SQLite DB with schema matching what ToolRegistry actually queries."""
    db_file = tmp_path / "agent_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE champions (
            id TEXT PRIMARY KEY,
            name_zh TEXT,
            name_en TEXT,
            cost INTEGER,
            icon_path TEXT
        );
        CREATE TABLE traits (
            id TEXT PRIMARY KEY,
            name_zh TEXT,
            name_en TEXT
        );
        CREATE TABLE items (
            id TEXT PRIMARY KEY,
            name_zh TEXT,
            name_en TEXT,
            icon_path TEXT
        );
        CREATE TABLE champion_traits (
            champion_id TEXT REFERENCES champions(id),
            trait_id TEXT REFERENCES traits(id)
        );

        -- Seed data
        INSERT INTO champions VALUES ('TFT17_Yasuo', '亚索', 'Yasuo', 5, 'champions/yasuo.png');
        INSERT INTO champions VALUES ('TFT17_Zed', '劫', 'Zed', 4, 'champions/zed.png');
        INSERT INTO champions VALUES ('TFT17_Lux', '拉克丝', 'Lux', 3, 'champions/lux.png');

        INSERT INTO traits VALUES ('TFT17_Trait_DarkStar', '暗星', 'Dark Star');
        INSERT INTO traits VALUES ('TFT17_Trait_Blademaster', '剑圣', 'Blademaster');
        INSERT INTO traits VALUES ('TFT17_Trait_Sorcerer', '法师', 'Sorcerer');

        INSERT INTO items VALUES ('TFT_Item_BFSword', '暴风大剑', 'B.F. Sword', 'items/bfsword.png');
        INSERT INTO items VALUES ('TFT_Item_InfinityEdge', '无尽之刃', 'Infinity Edge', 'items/ie.png');
        INSERT INTO items VALUES ('TFT_Item_EmptyBag', '空', 'EmptyBag', '');

        INSERT INTO champion_traits VALUES ('TFT17_Yasuo', 'TFT17_Trait_DarkStar');
        INSERT INTO champion_traits VALUES ('TFT17_Yasuo', 'TFT17_Trait_Blademaster');
        INSERT INTO champion_traits VALUES ('TFT17_Zed', 'TFT17_Trait_DarkStar');
        INSERT INTO champion_traits VALUES ('TFT17_Zed', 'TFT17_Trait_Blademaster');
        INSERT INTO champion_traits VALUES ('TFT17_Lux', 'TFT17_Trait_DarkStar');
        INSERT INTO champion_traits VALUES ('TFT17_Lux', 'TFT17_Trait_Sorcerer');
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def registry(agent_db):
    """ToolRegistry with mocked CompQuery/ItemQuery (heavy services)."""
    with (
        patch("api.services.comp_query.CompQuery") as mock_cq,
        patch("api.services.item_query.ItemQuery") as mock_iq,
    ):
        from api.agent.tools import ToolRegistry

        reg = ToolRegistry(agent_db)
        # Expose mocks for assertions
        reg._mock_comp_q = mock_cq.return_value
        reg._mock_item_q = mock_iq.return_value
        yield reg


# ---------------------------------------------------------------------------
# TestToolRegistryBasics
# ---------------------------------------------------------------------------


class TestToolRegistryBasics:
    """Registration, schema export, and name listing."""

    def test_all_11_tools_registered(self, registry):
        names = registry.tool_names()
        assert len(names) == 11

    def test_expected_tool_names(self, registry):
        expected = {
            "query_comps",
            "query_items",
            "query_specific",
            "search_items",
            "rag_search",
            "graph_query",
            "get_champion_info",
            "get_trait_info",
            "get_item_info",
            "calc_synergy",
            "get_version_meta",
        }
        assert set(registry.tool_names()) == expected

    def test_openai_schemas_structure(self, registry):
        schemas = registry.openai_schemas()
        assert len(schemas) == 11
        for schema in schemas:
            assert schema["type"] == "function"
            func = schema["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"

    def test_openai_schemas_have_required_field(self, registry):
        schemas = registry.openai_schemas()
        for schema in schemas:
            params = schema["function"]["parameters"]
            assert "required" in params


# ---------------------------------------------------------------------------
# TestExecute
# ---------------------------------------------------------------------------


class TestExecute:
    """ToolRegistry.execute() dispatch and error handling."""

    def test_unknown_tool_returns_error(self, registry):
        result = registry.execute("nonexistent_tool", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]
        assert result["data"] is None

    def test_tool_exception_returns_error(self, registry):
        # Make CompQuery.query raise
        registry._mock_comp_q.query.side_effect = RuntimeError("DB exploded")
        result = registry.execute("query_comps", {"champion_ids": ["TFT17_Yasuo"]})
        assert result["success"] is False
        assert "DB exploded" in result["error"]

    def test_query_comps_success(self, registry):
        registry._mock_comp_q.query.return_value = [{"comp_id": "c1", "champions": ["Yasuo"]}]
        result = registry.execute("query_comps", {"champion_ids": ["TFT17_Yasuo"]})
        assert result["success"] is True
        assert result["data"] == [{"comp_id": "c1", "champions": ["Yasuo"]}]
        registry._mock_comp_q.query.assert_called_once_with(["TFT17_Yasuo"])

    def test_query_items_filters_empty_bag(self, registry):
        registry._mock_item_q.query.return_value = [
            {"item_id": "TFT_Item_EmptyBag", "name_zh": "空"},
            {"item_id": "TFT_Item_InfinityEdge", "name_zh": "无尽之刃"},
        ]
        result = registry.execute("query_items", {"champion_id": "TFT17_Yasuo"})
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["item_id"] == "TFT_Item_InfinityEdge"

    def test_search_items_filters_empty(self, registry):
        registry._mock_item_q.search.return_value = [
            {"item_id": "EmptyBag", "name_zh": ""},
            {"item_id": "TFT_Item_BFSword", "name_zh": "暴风大剑"},
        ]
        result = registry.execute("search_items", {"keywords": ["暴风"]})
        assert result["success"] is True
        assert len(result["data"]) == 1


# ---------------------------------------------------------------------------
# TestSQLiteTools (direct DB queries, no mocks)
# ---------------------------------------------------------------------------


class TestSQLiteTools:
    """Tools that query SQLite directly: champion/trait/item/synergy/meta."""

    def test_get_champion_info_found(self, registry):
        result = registry.execute("get_champion_info", {"champion_id": "TFT17_Yasuo"})
        assert result["success"] is True
        data = result["data"]
        assert data["id"] == "TFT17_Yasuo"
        assert data["name_zh"] == "亚索"
        assert data["cost"] == 5
        assert set(data["traits"]) == {"暗星", "剑圣"}

    def test_get_champion_info_not_found(self, registry):
        result = registry.execute("get_champion_info", {"champion_id": "TFT17_NonExist"})
        assert result["success"] is True
        assert result["data"] is None

    def test_get_trait_info_found(self, registry):
        result = registry.execute("get_trait_info", {"trait_name": "暗星"})
        assert result["success"] is True
        data = result["data"]
        assert data["name_zh"] == "暗星"
        assert data["name_en"] == "Dark Star"
        member_ids = {m["id"] for m in data["members"]}
        assert member_ids == {"TFT17_Yasuo", "TFT17_Zed", "TFT17_Lux"}

    def test_get_trait_info_not_found(self, registry):
        result = registry.execute("get_trait_info", {"trait_name": "不存在的羁绊"})
        assert result["success"] is True
        assert result["data"] is None

    def test_get_item_info_found(self, registry):
        result = registry.execute("get_item_info", {"item_name": "暴风大剑"})
        assert result["success"] is True
        data = result["data"]
        assert data["name_zh"] == "暴风大剑"
        assert data["name_en"] == "B.F. Sword"

    def test_get_item_info_fuzzy_match(self, registry):
        result = registry.execute("get_item_info", {"item_name": "无尽"})
        assert result["success"] is True
        assert result["data"]["name_zh"] == "无尽之刃"

    def test_get_item_info_not_found(self, registry):
        result = registry.execute("get_item_info", {"item_name": "不存在的装备"})
        assert result["success"] is True
        assert result["data"] is None

    def test_calc_synergy_shared_traits(self, registry):
        result = registry.execute(
            "calc_synergy", {"champion_a": "TFT17_Yasuo", "champion_b": "TFT17_Zed"}
        )
        assert result["success"] is True
        data = result["data"]
        assert data["synergy_count"] == 2
        assert set(data["shared_traits"]) == {"暗星", "剑圣"}

    def test_calc_synergy_partial_overlap(self, registry):
        result = registry.execute(
            "calc_synergy", {"champion_a": "TFT17_Yasuo", "champion_b": "TFT17_Lux"}
        )
        assert result["success"] is True
        data = result["data"]
        # Yasuo: 暗星+剑圣, Lux: 暗星+法师 → shared: 暗星
        assert data["synergy_count"] == 1
        assert data["shared_traits"] == ["暗星"]

    def test_calc_synergy_no_overlap(self, registry):
        # Zed: 暗星+剑圣, Lux: 暗星+法师 → they share 暗星
        # Create a champion with no overlapping traits for true zero case
        registry._conn.execute(
            "INSERT INTO champions VALUES ('TFT17_Solo', '独行侠', 'Solo', 1, 'x.png')"
        )
        registry._conn.commit()
        result = registry.execute(
            "calc_synergy", {"champion_a": "TFT17_Yasuo", "champion_b": "TFT17_Solo"}
        )
        assert result["success"] is True
        assert result["data"]["synergy_count"] == 0
        assert result["data"]["shared_traits"] == []

    def test_get_version_meta(self, registry):
        result = registry.execute("get_version_meta", {})
        assert result["success"] is True
        data = result["data"]
        assert data["set"] == "Set 17 Space Gods"
        assert data["total_champions"] == 3
        assert data["total_traits"] == 3
        assert "5费" in data["cost_distribution"]
        assert data["cost_distribution"]["5费"] == 1


# ---------------------------------------------------------------------------
# TestGracefulDegradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """RAG and Graph tools degrade gracefully when services unavailable."""

    def test_rag_search_unavailable(self, registry):
        # Without Milvus running, should return a friendly error dict
        result = registry.execute("rag_search", {"query": "亚索阵容"})
        assert result["success"] is True
        data = result["data"]
        assert isinstance(data, list)
        assert len(data) == 1
        assert "暂不可用" in data[0]["content"]

    def test_graph_query_unavailable(self, registry):
        result = registry.execute("graph_query", {"champion_name": "亚索"})
        assert result["success"] is True
        data = result["data"]
        assert isinstance(data, list)
        assert len(data) == 1
        assert "暂不可用" in data[0]["error"]


# ---------------------------------------------------------------------------
# TestFilterEmpty (module-level helper)
# ---------------------------------------------------------------------------


class TestFilterEmptyHelper:
    """Verify _filter_empty removes placeholder items."""

    def test_removes_all_empty_variants(self):
        from api.agent.tools import _filter_empty

        items = [
            {"item_id": "TFT_Item_EmptyBag", "name_zh": "空1"},
            {"item_id": "EmptyBag", "name_zh": "空2"},
            {"item_id": "", "name_zh": "空3"},
            {"item_id": "TFT_Item_Real", "name_zh": "真装备"},
        ]
        filtered = _filter_empty(items)
        assert len(filtered) == 1
        assert filtered[0]["item_id"] == "TFT_Item_Real"

    def test_no_item_id_key_treated_as_empty(self):
        from api.agent.tools import _filter_empty

        items = [{"name_zh": "无ID"}, {"item_id": "TFT_Item_X", "name_zh": "有ID"}]
        filtered = _filter_empty(items)
        # Missing key → .get returns "" → filtered out
        assert len(filtered) == 1
