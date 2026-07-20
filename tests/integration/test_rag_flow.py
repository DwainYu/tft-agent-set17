"""Integration tests for RAG endpoints using httpx AsyncClient."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from api.services.rag.reranker import ScoredDocument

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag_engine():
    """A mock RAGEngine that returns predictable scored documents."""
    engine = MagicMock()
    engine.query.return_value = (
        [
            ScoredDocument(content="Akali best items", score=0.95, metadata={"champion_id": "akali", "doc_type": "champion"}),
            ScoredDocument(content="Akali synergies", score=0.82, metadata={"champion_id": "akali", "doc_type": "trait"}),
        ],
        42,
    )
    return engine


@pytest.fixture
def mock_graph_store_healthy():
    """A mock GraphStore that is healthy and returns records."""
    store = MagicMock()
    store.is_healthy.return_value = True
    store.run_cypher.return_value = [
        {"champion": "zed", "shared_traits": ["assassin"], "count": 2},
        {"champion": "katarina", "shared_traits": ["assassin", "battle_academia"], "count": 2},
    ]
    return store


@pytest.fixture
def mock_graph_store_unhealthy():
    """A mock GraphStore that reports unhealthy."""
    store = MagicMock()
    store.is_healthy.return_value = False
    return store


# ---------------------------------------------------------------------------
# TestRagEndpoint
# ---------------------------------------------------------------------------

class TestRagEndpoint:

    async def test_rag_query_returns_200(self, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_rag_engine):
        import api.routers.rag as rag_module
        monkeypatch.setattr(rag_module, "get_rag_engine", lambda: mock_rag_engine)

        resp = await api_client.post(
            "/internal/rag/query",
            json={"query": "akali build", "top_k": 5, "hybrid": True, "rerank": True},
        )
        assert resp.status_code == 200

    async def test_rag_query_response_shape(self, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_rag_engine):
        import api.routers.rag as rag_module
        monkeypatch.setattr(rag_module, "get_rag_engine", lambda: mock_rag_engine)

        resp = await api_client.post(
            "/internal/rag/query",
            json={"query": "akali items"},
        )
        data = resp.json()

        assert "documents" in data
        assert "latency_ms" in data
        assert isinstance(data["documents"], list)
        assert len(data["documents"]) == 2

        doc = data["documents"][0]
        assert "id" in doc
        assert "score" in doc
        assert "content" in doc
        assert "metadata" in doc
        assert isinstance(doc["score"], float)
        assert isinstance(doc["metadata"], dict)
        assert data["latency_ms"] == 42

    async def test_rag_query_validation_error(self, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_rag_engine):
        import api.routers.rag as rag_module
        monkeypatch.setattr(rag_module, "get_rag_engine", lambda: mock_rag_engine)

        resp = await api_client.post(
            "/internal/rag/query",
            json={"query": "", "top_k": 5},
        )
        assert resp.status_code == 422

    async def test_rag_query_respects_top_k(self, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_rag_engine):
        import api.routers.rag as rag_module
        monkeypatch.setattr(rag_module, "get_rag_engine", lambda: mock_rag_engine)

        await api_client.post(
            "/internal/rag/query",
            json={"query": "akali comp", "top_k": 10},
        )

        # Verify top_k was forwarded to the engine
        call_kwargs = mock_rag_engine.query.call_args[1]
        assert call_kwargs["top_k"] == 10


# ---------------------------------------------------------------------------
# TestGraphEndpoint
# ---------------------------------------------------------------------------

class TestGraphEndpoint:

    async def test_graph_query_neo4j_unavailable_returns_503(
        self,
        api_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        mock_graph_store_unhealthy,
    ):
        import api.routers.rag as rag_module
        monkeypatch.setattr(rag_module, "get_graph_store", lambda: mock_graph_store_unhealthy)

        resp = await api_client.post(
            "/internal/graph/query",
            json={"cypher": "MATCH (n) RETURN n LIMIT 5"},
        )
        assert resp.status_code == 503

    async def test_graph_query_validation_error(self, api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_graph_store_healthy):
        import api.routers.rag as rag_module
        monkeypatch.setattr(rag_module, "get_graph_store", lambda: mock_graph_store_healthy)

        resp = await api_client.post(
            "/internal/graph/query",
            json={"cypher": ""},
        )
        assert resp.status_code == 422
