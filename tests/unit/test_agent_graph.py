"""Unit tests for api.agent.graph / api.agent.nodes — LangGraph StateGraph."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_db(tmp_path: Path) -> sqlite3.Connection:
    """Minimal SQLite DB for agent node tests."""
    db_file = tmp_path / "graph_test.db"
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
        CREATE TABLE aliases (
            alias TEXT PRIMARY KEY,
            champion_id TEXT REFERENCES champions(id)
        );

        INSERT INTO champions VALUES ('TFT17_Yasuo', '亚索', 'Yasuo', 5, 'c/yasuo.png');
        INSERT INTO champions VALUES ('TFT17_Zed', '劫', 'Zed', 4, 'c/zed.png');
        INSERT INTO traits VALUES ('TFT17_Trait_DarkStar', '暗星', 'Dark Star');
        INSERT INTO traits VALUES ('TFT17_Trait_Blademaster', '剑圣', 'Blademaster');
        INSERT INTO champion_traits VALUES ('TFT17_Yasuo', 'TFT17_Trait_DarkStar');
        INSERT INTO champion_traits VALUES ('TFT17_Yasuo', 'TFT17_Trait_Blademaster');
        INSERT INTO champion_traits VALUES ('TFT17_Zed', 'TFT17_Trait_DarkStar');
        INSERT INTO aliases VALUES ('亚索', 'TFT17_Yasuo');
        INSERT INTO aliases VALUES ('yasuo', 'TFT17_Yasuo');
    """)
    conn.commit()
    yield conn
    conn.close()


def _make_state(**overrides) -> dict[str, Any]:
    """Build a minimal AgentState dict with sensible defaults."""
    base: dict[str, Any] = {
        "messages": [],
        "question": "亚索主C阵容",
        "direction": None,
        "entities": [],
        "plan": [],
        "tool_results": [],
        "critique": "",
        "should_retry": False,
        "iteration": 0,
        "final_answer": "",
        "card_data": None,
        "error": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestShouldRetry (conditional edge routing)
# ---------------------------------------------------------------------------


class TestShouldRetry:
    """Verify the conditional edge routing function."""

    def test_returns_done_when_false(self):
        from api.agent.nodes import should_retry

        state = _make_state(should_retry=False)
        assert should_retry(state) == "done"

    def test_returns_retry_when_true(self):
        from api.agent.nodes import should_retry

        state = _make_state(should_retry=True)
        assert should_retry(state) == "retry"

    def test_defaults_to_done_when_missing(self):
        from api.agent.nodes import should_retry

        state = _make_state()
        del state["should_retry"]
        assert should_retry(state) == "done"


# ---------------------------------------------------------------------------
# TestPlannerNode (rule-based path)
# ---------------------------------------------------------------------------


class TestPlannerNode:
    """Planner node with LLM disabled (rule-based fallback)."""

    @patch("api.agent.nodes.get_llm", return_value=None)
    @patch("api.agent.nodes._get_conn")
    def test_rule_based_plan_produces_plan(self, mock_get_conn, _mock_llm, agent_db):
        from api.agent.nodes import planner_node

        mock_get_conn.return_value = agent_db
        state = _make_state(
            question="亚索主C阵容",
            entities=[{"type": "champion", "canonical_id": "TFT17_Yasuo", "name_zh": "亚索"}],
        )

        with patch("api.agent.nodes._rule_based_plan") as mock_plan:
            mock_plan.return_value = [
                {"tool": "query_comps", "args": {"champion_ids": ["TFT17_Yasuo"]}, "reason": "test"}
            ]
            result = planner_node(state)

        assert "plan" in result
        assert len(result["plan"]) == 1
        assert result["plan"][0]["tool"] == "query_comps"
        assert result["iteration"] == 1
        assert len(result["messages"]) == 1

    @patch("api.agent.nodes.get_llm", return_value=None)
    @patch("api.agent.nodes._rule_based_plan")
    def test_iteration_increments(self, mock_plan, _mock_llm):
        from api.agent.nodes import planner_node

        mock_plan.return_value = [{"tool": "query_comps", "args": {}, "reason": "r"}]
        state = _make_state(iteration=2)
        result = planner_node(state)
        assert result["iteration"] == 3


# ---------------------------------------------------------------------------
# TestExecutorNode
# ---------------------------------------------------------------------------


class TestExecutorNode:
    """Executor node — executes planned tools."""

    @patch("api.agent.nodes._get_conn")
    def test_executes_plan(self, mock_get_conn, agent_db):
        from api.agent.nodes import executor_node

        mock_get_conn.return_value = agent_db
        state = _make_state(
            plan=[
                {"tool": "get_champion_info", "args": {"champion_id": "TFT17_Yasuo"}, "reason": "test"},
            ]
        )

        with patch("api.agent.nodes._get_registry") as mock_reg:
            mock_registry = MagicMock()
            mock_registry.execute.return_value = {
                "success": True,
                "data": {"id": "TFT17_Yasuo", "name_zh": "亚索"},
                "error": None,
            }
            mock_reg.return_value = mock_registry
            result = executor_node(state)

        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["success"] is True
        assert result["tool_results"][0]["tool"] == "get_champion_info"
        mock_registry.execute.assert_called_once_with(
            "get_champion_info", {"champion_id": "TFT17_Yasuo"}
        )

    @patch("api.agent.nodes._get_conn")
    def test_empty_plan_returns_empty_results(self, mock_get_conn, agent_db):
        from api.agent.nodes import executor_node

        mock_get_conn.return_value = agent_db
        state = _make_state(plan=[])
        result = executor_node(state)
        assert result["tool_results"] == []

    @patch("api.agent.nodes._get_conn")
    def test_multiple_tools_executed_in_order(self, mock_get_conn, agent_db):
        from api.agent.nodes import executor_node

        mock_get_conn.return_value = agent_db
        state = _make_state(
            plan=[
                {"tool": "get_champion_info", "args": {"champion_id": "TFT17_Yasuo"}, "reason": "a"},
                {"tool": "get_version_meta", "args": {}, "reason": "b"},
            ]
        )

        with patch("api.agent.nodes._get_registry") as mock_reg:
            mock_registry = MagicMock()
            mock_registry.execute.side_effect = [
                {"success": True, "data": {"name_zh": "亚索"}, "error": None},
                {"success": True, "data": {"set": "Set 17"}, "error": None},
            ]
            mock_reg.return_value = mock_registry
            result = executor_node(state)

        assert len(result["tool_results"]) == 2
        assert result["tool_results"][0]["tool"] == "get_champion_info"
        assert result["tool_results"][1]["tool"] == "get_version_meta"


# ---------------------------------------------------------------------------
# TestCriticNode (rule-based path)
# ---------------------------------------------------------------------------


class TestCriticNode:
    """Critic node — heuristic evaluation without LLM."""

    @patch("api.agent.nodes.get_llm", return_value=None)
    @patch("api.agent.nodes.get_settings")
    def test_pass_when_data_present(self, mock_settings, _mock_llm):
        from api.agent.nodes import critic_node

        mock_settings.return_value = MagicMock(AGENT_MAX_ITERATIONS=3)
        state = _make_state(
            iteration=1,
            tool_results=[{"success": True, "data": [{"comp": "x"}], "tool": "query_comps"}],
        )
        result = critic_node(state)
        assert result["should_retry"] is False
        assert "有效" in result["critique"]

    @patch("api.agent.nodes.get_llm", return_value=None)
    @patch("api.agent.nodes.get_settings")
    def test_retry_when_all_empty(self, mock_settings, _mock_llm):
        from api.agent.nodes import critic_node

        mock_settings.return_value = MagicMock(AGENT_MAX_ITERATIONS=3)
        state = _make_state(
            iteration=1,
            tool_results=[{"success": True, "data": [], "tool": "query_comps"}],
        )
        result = critic_node(state)
        assert result["should_retry"] is True

    @patch("api.agent.nodes.get_llm", return_value=None)
    @patch("api.agent.nodes.get_settings")
    def test_retry_when_all_failed(self, mock_settings, _mock_llm):
        from api.agent.nodes import critic_node

        mock_settings.return_value = MagicMock(AGENT_MAX_ITERATIONS=3)
        state = _make_state(
            iteration=1,
            tool_results=[{"success": False, "data": None, "error": "boom", "tool": "x"}],
        )
        result = critic_node(state)
        assert result["should_retry"] is True

    @patch("api.agent.nodes.get_llm", return_value=None)
    @patch("api.agent.nodes.get_settings")
    def test_max_iteration_stops_retry(self, mock_settings, _mock_llm):
        from api.agent.nodes import critic_node

        mock_settings.return_value = MagicMock(AGENT_MAX_ITERATIONS=3)
        state = _make_state(
            iteration=3,
            tool_results=[{"success": False, "data": None, "error": "x", "tool": "y"}],
        )
        result = critic_node(state)
        assert result["should_retry"] is False
        assert "最大迭代" in result["critique"]


# ---------------------------------------------------------------------------
# TestReflectNode (template path)
# ---------------------------------------------------------------------------


class TestReflectNode:
    """Reflect node — template-based answer composition."""

    @patch("api.agent.nodes.get_llm", return_value=None)
    def test_no_results_gives_fallback_message(self, _mock_llm):
        from api.agent.nodes import reflect_node

        state = _make_state(tool_results=[])
        result = reflect_node(state)
        assert "没有找到" in result["final_answer"]
        assert result["card_data"] is None

    @patch("api.agent.nodes.get_llm", return_value=None)
    def test_query_comps_extracts_card_data(self, _mock_llm):
        from api.agent.nodes import reflect_node

        comp_data = [{"comp_id": "c1", "champions": ["亚索", "劫"]}]
        state = _make_state(
            tool_results=[
                {"success": True, "data": comp_data, "tool": "query_comps", "reason": ""}
            ]
        )
        result = reflect_node(state)
        assert result["card_data"] == comp_data[0]
        assert "1 个阵容" in result["final_answer"]

    @patch("api.agent.nodes.get_llm", return_value=None)
    def test_champion_info_in_answer(self, _mock_llm):
        from api.agent.nodes import reflect_node

        state = _make_state(
            tool_results=[
                {
                    "success": True,
                    "data": {"name_zh": "亚索", "cost": 5, "traits": ["暗星", "剑圣"]},
                    "tool": "get_champion_info",
                    "reason": "",
                }
            ]
        )
        result = reflect_node(state)
        assert "亚索" in result["final_answer"]
        assert "5费" in result["final_answer"]

    @patch("api.agent.nodes.get_llm", return_value=None)
    def test_version_meta_in_answer(self, _mock_llm):
        from api.agent.nodes import reflect_node

        state = _make_state(
            tool_results=[
                {
                    "success": True,
                    "data": {"set": "Set 17 Space Gods", "total_champions": 63},
                    "tool": "get_version_meta",
                    "reason": "",
                }
            ]
        )
        result = reflect_node(state)
        assert "Set 17 Space Gods" in result["final_answer"]
        assert "63" in result["final_answer"]

    @patch("api.agent.nodes.get_llm", return_value=None)
    def test_failed_results_ignored(self, _mock_llm):
        from api.agent.nodes import reflect_node

        state = _make_state(
            tool_results=[
                {"success": False, "data": None, "error": "x", "tool": "query_comps", "reason": ""}
            ]
        )
        result = reflect_node(state)
        assert "没有找到" in result["final_answer"]


# ---------------------------------------------------------------------------
# TestGraphTopology
# ---------------------------------------------------------------------------


class TestGraphTopology:
    """Verify the StateGraph is wired correctly."""

    def test_build_graph_has_4_nodes(self):
        from api.agent.graph import build_agent_graph

        graph = build_agent_graph()
        # StateGraph stores nodes in .nodes dict
        node_names = set(graph.nodes.keys())
        assert {"planner", "executor", "critic", "reflect"} <= node_names

    def test_compile_agent_runs(self):
        """compile_agent produces a runnable compiled graph."""
        from api.agent.graph import compile_agent

        app = compile_agent(checkpointer=None, interrupt_before_executor=False)
        assert app is not None
        # Compiled graph should have an invoke method
        assert hasattr(app, "invoke")

    def test_compile_with_interrupt(self):
        """compile_agent with interrupt_before_executor=True still compiles."""
        from api.agent.graph import compile_agent

        app = compile_agent(checkpointer=None, interrupt_before_executor=True)
        assert app is not None


# ---------------------------------------------------------------------------
# TestEndToEnd (rule-based, no LLM, no external services)
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Full graph invocation with mocked internals (no LLM, no Milvus/Neo4j)."""

    @patch("api.agent.nodes.get_llm", return_value=None)
    @patch("api.agent.nodes._get_conn")
    @patch("api.agent.nodes.get_settings")
    def test_full_pipeline_produces_final_answer(
        self, mock_settings, mock_get_conn, _mock_llm, agent_db
    ):
        from api.agent.graph import compile_agent

        mock_settings.return_value = MagicMock(
            AGENT_MAX_ITERATIONS=3, DB_PATH=str(agent_db)
        )
        mock_get_conn.return_value = agent_db

        app = compile_agent(checkpointer=None, interrupt_before_executor=False)

        # Patch _rule_based_plan to avoid needing IntentRouter
        with patch("api.agent.nodes._rule_based_plan") as mock_plan:
            mock_plan.return_value = [
                {"tool": "get_champion_info", "args": {"champion_id": "TFT17_Yasuo"}, "reason": "test"}
            ]
            initial_state = _make_state(
                question="亚索什么羁绊",
                entities=[{"type": "champion", "canonical_id": "TFT17_Yasuo", "name_zh": "亚索"}],
            )
            result = app.invoke(initial_state)

        assert result["final_answer"] != ""
        assert result["iteration"] >= 1
        assert len(result["tool_results"]) >= 1
        # The champion info tool should have returned real data from agent_db
        champ_result = result["tool_results"][0]
        assert champ_result["success"] is True
        assert champ_result["data"]["name_zh"] == "亚索"

    @patch("api.agent.nodes.get_llm", return_value=None)
    @patch("api.agent.nodes._get_conn")
    @patch("api.agent.nodes.get_settings")
    def test_retry_loop_terminates_at_max_iterations(
        self, mock_settings, mock_get_conn, _mock_llm, agent_db
    ):
        from api.agent.graph import compile_agent

        mock_settings.return_value = MagicMock(
            AGENT_MAX_ITERATIONS=2, DB_PATH=str(agent_db)
        )
        mock_get_conn.return_value = agent_db

        app = compile_agent(checkpointer=None, interrupt_before_executor=False)

        # Plan always returns a tool that yields empty data → critic retries
        with patch("api.agent.nodes._rule_based_plan") as mock_plan:
            mock_plan.return_value = [
                {"tool": "get_champion_info", "args": {"champion_id": "TFT17_NonExist"}, "reason": "x"}
            ]
            initial_state = _make_state(question="不存在的英雄")
            result = app.invoke(initial_state)

        # Should not exceed max iterations
        assert result["iteration"] <= 2
        assert result["final_answer"] != ""


# ---------------------------------------------------------------------------
# TestLLMPath (mocked LLM)
# ---------------------------------------------------------------------------


class TestLLMPlannerPath:
    """Planner with a mocked LLM returning tool_calls."""

    @patch("api.agent.nodes._get_conn")
    @patch("api.agent.nodes.get_llm")
    def test_llm_tool_calls_parsed(self, mock_get_llm, mock_get_conn, agent_db):
        from api.agent.nodes import planner_node

        mock_get_conn.return_value = agent_db

        # Mock LLM that returns tool_calls
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = [
            {"name": "get_champion_info", "args": {"champion_id": "TFT17_Yasuo"}}
        ]
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        state = _make_state(question="亚索信息")
        result = planner_node(state)

        assert len(result["plan"]) == 1
        assert result["plan"][0]["tool"] == "get_champion_info"
        assert result["iteration"] == 1

    @patch("api.agent.nodes._get_conn")
    @patch("api.agent.nodes.get_llm")
    @patch("api.agent.nodes._rule_based_plan")
    def test_llm_failure_falls_back_to_rules(self, mock_plan, mock_get_llm, mock_get_conn, agent_db):
        from api.agent.nodes import planner_node

        mock_get_conn.return_value = agent_db
        mock_plan.return_value = [{"tool": "query_comps", "args": {}, "reason": "fallback"}]

        # LLM that raises
        mock_llm = MagicMock()
        mock_llm.bind_tools.side_effect = RuntimeError("connection refused")
        mock_get_llm.return_value = mock_llm

        state = _make_state(question="测试")
        result = planner_node(state)

        assert result["plan"][0]["tool"] == "query_comps"
        mock_plan.assert_called_once()


# ---------------------------------------------------------------------------
# TestParsePlanFromText
# ---------------------------------------------------------------------------


class TestParsePlanFromText:
    """Verify JSON plan extraction from LLM text output."""

    def test_valid_json_array(self):
        from api.agent.nodes import _parse_plan_from_text

        text = '好的，我来查询：[{"tool": "get_champion_info", "args": {"champion_id": "TFT17_Yasuo"}, "reason": "查询亚索"}]'
        plan = _parse_plan_from_text(text)
        assert len(plan) == 1
        assert plan[0]["tool"] == "get_champion_info"

    def test_no_json_returns_empty(self):
        from api.agent.nodes import _parse_plan_from_text

        plan = _parse_plan_from_text("没有JSON内容")
        assert plan == []

    def test_malformed_json_returns_empty(self):
        from api.agent.nodes import _parse_plan_from_text

        plan = _parse_plan_from_text('[{"tool": broken]')
        assert plan == []

    def test_multiple_tools(self):
        from api.agent.nodes import _parse_plan_from_text

        text = '[{"tool": "a", "args": {}}, {"tool": "b", "args": {"x": 1}}]'
        plan = _parse_plan_from_text(text)
        assert len(plan) == 2
        assert plan[0]["tool"] == "a"
        assert plan[1]["tool"] == "b"
