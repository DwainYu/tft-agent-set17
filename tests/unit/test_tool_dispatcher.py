"""Unit tests for api.services.tool_dispatcher.ToolDispatcher."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.services.tool_dispatcher import ToolDispatcher

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_conn():
    """A mock SQLite connection (never actually queried)."""
    return MagicMock()


@pytest.fixture
def dispatcher(mock_conn):
    """ToolDispatcher with mocked underlying query services."""
    with (
        patch("api.services.tool_dispatcher.CompQuery") as mock_cq,
        patch("api.services.tool_dispatcher.ItemQuery") as mock_iq,
    ):
        d = ToolDispatcher(mock_conn)
        d._comp_query = mock_cq.return_value
        d._item_query = mock_iq.return_value
        yield d


class TestDispatchRouting:
    """Verify dispatch routes to the correct query method."""

    def test_query_comps_calls_comp_query(self, dispatcher):
        dispatcher._comp_query.query.return_value = [{"comp_id": "c1"}]
        entities = [{"type": "champion", "canonical_id": "garen"}]

        results = dispatcher.dispatch("query_comps", entities)

        dispatcher._comp_query.query.assert_called_once_with(["garen"])
        assert results == [{"comp_id": "c1"}]

    def test_query_items_by_ids(self, dispatcher):
        dispatcher._item_query.query_by_ids.return_value = [
            {"item_id": "TFT_Item_001", "name_zh": "暴风大剑"},
        ]
        entities = [{"type": "item", "canonical_id": "TFT_Item_001"}]

        results = dispatcher.dispatch("query_items", entities)

        dispatcher._item_query.query_by_ids.assert_called_once_with(["TFT_Item_001"])
        assert len(results) == 1

    def test_query_items_by_champion(self, dispatcher):
        dispatcher._item_query.query.return_value = [
            {"item_id": "TFT_Item_002", "name_zh": "无尽之刃"},
        ]
        entities = [{"type": "champion", "canonical_id": "jinx"}]

        dispatcher.dispatch("query_items", entities)

        dispatcher._item_query.query.assert_called_once_with("jinx")

    def test_search_items(self, dispatcher):
        dispatcher._item_query.search.return_value = [
            {"item_id": "TFT_Item_003", "name_zh": "暴风大剑"},
        ]
        entities = [{"type": "item", "name_zh": "暴风", "canonical_id": "TFT_Item_003"}]

        results = dispatcher.dispatch("search_items", entities)

        dispatcher._item_query.search.assert_called_once_with(["暴风"])
        assert len(results) == 1

    def test_query_specific_with_champion(self, dispatcher):
        dispatcher._item_query.query.return_value = [
            {"item_id": "TFT_Item_004", "name_zh": "巨人杀手"},
        ]
        entities = [{"type": "champion", "canonical_id": "garen"}]

        dispatcher.dispatch("query_specific", entities)

        dispatcher._item_query.query.assert_called_once_with("garen")

    def test_unknown_tool_returns_empty(self, dispatcher):
        results = dispatcher.dispatch("unknown_tool", [{"type": "champion", "canonical_id": "x"}])
        assert results == []


class TestDispatchEmptyEntities:
    """Verify behaviour when entities list is empty."""

    def test_query_comps_empty_entities(self, dispatcher):
        dispatcher._comp_query.query.return_value = []
        results = dispatcher.dispatch("query_comps", [])
        dispatcher._comp_query.query.assert_called_once_with([])
        assert results == []

    def test_query_items_empty_entities(self, dispatcher):
        dispatcher._item_query.query.return_value = []
        dispatcher.dispatch("query_items", [])
        dispatcher._item_query.query.assert_called_once_with(None)

    def test_search_items_empty_entities(self, dispatcher):
        dispatcher._item_query.query.return_value = [{"item_id": "all"}]
        dispatcher.dispatch("search_items", [])
        # Falls back to query(None) when no keywords
        dispatcher._item_query.query.assert_called_once_with(None)

    def test_query_specific_empty_entities(self, dispatcher):
        results = dispatcher.dispatch("query_specific", [])
        assert results == []


class TestFilterEmpty:
    """Verify _filter_empty removes EmptyBag entries."""

    def test_removes_empty_bag(self):
        results = [
            {"item_id": "TFT_Item_EmptyBag", "name_zh": "空"},
            {"item_id": "TFT_Item_001", "name_zh": "暴风大剑"},
        ]
        filtered = ToolDispatcher._filter_empty(results)
        assert len(filtered) == 1
        assert filtered[0]["item_id"] == "TFT_Item_001"

    def test_removes_empty_bag_short_name(self):
        results = [
            {"item_id": "EmptyBag", "name_zh": "空"},
            {"item_id": "TFT_Item_002", "name_zh": "无尽之刃"},
        ]
        filtered = ToolDispatcher._filter_empty(results)
        assert len(filtered) == 1

    def test_removes_empty_item_id(self):
        results = [
            {"item_id": "", "name_zh": "空"},
            {"item_id": "TFT_Item_003", "name_zh": "巨人杀手"},
        ]
        filtered = ToolDispatcher._filter_empty(results)
        assert len(filtered) == 1

    def test_all_empty_returns_empty_list(self):
        results = [
            {"item_id": "TFT_Item_EmptyBag", "name_zh": "空"},
            {"item_id": "EmptyBag", "name_zh": "空2"},
            {"item_id": "", "name_zh": "空3"},
        ]
        filtered = ToolDispatcher._filter_empty(results)
        assert filtered == []

    def test_no_empty_entries_unchanged(self):
        results = [
            {"item_id": "TFT_Item_001", "name_zh": "暴风大剑"},
            {"item_id": "TFT_Item_002", "name_zh": "无尽之刃"},
        ]
        filtered = ToolDispatcher._filter_empty(results)
        assert filtered == results
