"""Unit tests for RAG Engine with mocked Milvus/Neo4j/Embedding/Reranker."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.services.rag.embedding import BGEEmbedding
from api.services.rag.engine import MilvusHit, MilvusStore, RAGEngine
from api.services.rag.graph_store import GraphStore
from api.services.rag.reranker import BGEReranker, ScoredDocument

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_milvus_hit(doc_id: str, score: float = 0.9, content: str = "text") -> MilvusHit:
    return MilvusHit(id=doc_id, score=score, content=content, metadata={"doc_type": "champion", "champion_id": "akali"})


def _make_search_result(doc_id: str, score: float = 0.9, content: str = "text") -> MagicMock:
    """Build a mock that behaves like a pymilvus search hit."""
    hit = MagicMock()
    hit.id = doc_id
    hit.score = score
    hit.entity.get = lambda key, default="": {
        "content": content,
        "doc_type": "champion",
        "champion_id": "akali",
    }.get(key, default)
    return hit


# ---------------------------------------------------------------------------
# TestMilvusStore
# ---------------------------------------------------------------------------

class TestMilvusStore:

    def test_dense_search_returns_hits(self):
        store = MilvusStore()
        mock_collection = MagicMock()
        mock_hit = _make_search_result("doc_1", score=0.95, content="Akali guide")
        mock_collection.search.return_value = [[mock_hit]]
        store._collection = mock_collection

        hits = store.dense_search([0.1] * 1024, top_k=5)

        assert len(hits) == 1
        assert isinstance(hits[0], MilvusHit)
        assert hits[0].id == "doc_1"
        assert hits[0].score == 0.95
        assert hits[0].content == "Akali guide"

    def test_sparse_search_returns_hits(self):
        store = MilvusStore()
        mock_collection = MagicMock()
        mock_hit = _make_search_result("doc_2", score=0.8, content="Item build")
        mock_collection.search.return_value = [[mock_hit]]
        store._collection = mock_collection

        hits = store.sparse_search({0: 1.5, 10: 0.3}, top_k=5)

        assert len(hits) == 1
        assert isinstance(hits[0], MilvusHit)
        assert hits[0].id == "doc_2"

    def test_dense_search_empty_collection(self):
        store = MilvusStore()
        # _collection is None by default
        hits = store.dense_search([0.1] * 1024, top_k=5)
        assert hits == []

    def test_sparse_search_empty_collection(self):
        store = MilvusStore()
        hits = store.sparse_search({0: 1.0}, top_k=5)
        assert hits == []

    def test_insert_returns_count(self):
        store = MilvusStore()
        store._collection = MagicMock()

        docs = [
            {"id": "d1", "content": "text1", "dense": [0.1], "sparse": {0: 1.0}, "doc_type": "a", "champion_id": "x"},
            {"id": "d2", "content": "text2", "dense": [0.2], "sparse": {1: 2.0}, "doc_type": "b", "champion_id": "y"},
            {"id": "d3", "content": "text3", "dense": [0.3], "sparse": {2: 3.0}, "doc_type": "c", "champion_id": "z"},
        ]
        count = store.insert(docs)

        assert count == 3
        store._collection.insert.assert_called_once()
        store._collection.flush.assert_called_once()


# ---------------------------------------------------------------------------
# TestRRF
# ---------------------------------------------------------------------------

class TestRRF:

    def test_fusion_merges_two_lists(self):
        list_a = [_fake_milvus_hit("d1", 0.9), _fake_milvus_hit("d2", 0.8), _fake_milvus_hit("d3", 0.7)]
        list_b = [_fake_milvus_hit("d2", 0.95), _fake_milvus_hit("d4", 0.6), _fake_milvus_hit("d1", 0.5)]

        fused = RAGEngine._reciprocal_rank_fusion(list_a, list_b, k=60)

        ids = [h.id for h in fused]
        # d1 and d2 appear in both lists, so they should have higher RRF scores
        assert "d1" in ids
        assert "d2" in ids
        assert "d3" in ids
        assert "d4" in ids
        # d1 is rank 0 in list_a and rank 2 in list_b => highest combined
        # d2 is rank 1 in list_a and rank 0 in list_b => also high
        # Both d1 and d2 should be above d3 and d4
        assert ids.index("d1") < ids.index("d3")
        assert ids.index("d2") < ids.index("d3")

        # Verify RRF score for d1: 1/(60+0+1) + 1/(60+2+1) = 1/61 + 1/63
        d1_hit = next(h for h in fused if h.id == "d1")
        expected_score = 1.0 / 61 + 1.0 / 63
        assert abs(d1_hit.score - expected_score) < 1e-9

    def test_fusion_single_list(self):
        single = [_fake_milvus_hit("a", 0.9), _fake_milvus_hit("b", 0.8), _fake_milvus_hit("c", 0.7)]

        fused = RAGEngine._reciprocal_rank_fusion(single, k=60)

        ids = [h.id for h in fused]
        # Order preserved: rank 0 > rank 1 > rank 2
        assert ids == ["a", "b", "c"]

    def test_fusion_empty_lists(self):
        fused = RAGEngine._reciprocal_rank_fusion([], [], k=60)
        assert fused == []


# ---------------------------------------------------------------------------
# TestRAGEngine
# ---------------------------------------------------------------------------

class TestRAGEngine:

    @pytest.fixture
    def mock_embedding(self):
        emb = MagicMock(spec=BGEEmbedding)
        emb.encode_query.return_value = {
            "dense": [0.1] * 1024,
            "sparse": {0: 1.5, 10: 0.3},
            "colbert_vecs": [[0.1] * 128],
        }
        return emb

    @pytest.fixture
    def mock_reranker(self):
        rr = MagicMock(spec=BGEReranker)
        rr.rerank.return_value = [
            ScoredDocument(content="top doc", score=0.95, metadata={"champion_id": "akali"}),
            ScoredDocument(content="second doc", score=0.80, metadata={"champion_id": ""}),
        ]
        return rr

    @pytest.fixture
    def mock_milvus(self):
        ms = MagicMock(spec=MilvusStore)
        ms.dense_search.return_value = [
            _fake_milvus_hit("d1", 0.9, "dense result 1"),
            _fake_milvus_hit("d2", 0.8, "dense result 2"),
        ]
        ms.sparse_search.return_value = [
            _fake_milvus_hit("d3", 0.85, "sparse result 1"),
            _fake_milvus_hit("d4", 0.75, "sparse result 2"),
        ]
        return ms

    def test_query_returns_scored_documents(self, mock_embedding, mock_reranker, mock_milvus):
        engine = RAGEngine(embedding=mock_embedding, reranker=mock_reranker, milvus=mock_milvus)

        scored, latency_ms = engine.query("test query", top_k=5, hybrid=True, rerank=True)

        assert isinstance(scored, list)
        assert len(scored) == 2
        assert isinstance(scored[0], ScoredDocument)
        assert scored[0].score == 0.95
        assert isinstance(latency_ms, int)
        assert latency_ms >= 0

    def test_query_without_hybrid_skips_sparse(self, mock_embedding, mock_reranker, mock_milvus):
        engine = RAGEngine(embedding=mock_embedding, reranker=mock_reranker, milvus=mock_milvus)

        engine.query("test query", top_k=5, hybrid=False, rerank=True)

        mock_milvus.sparse_search.assert_not_called()
        mock_milvus.dense_search.assert_called_once()

    def test_query_without_rerank_skips_reranker(self, mock_embedding, mock_reranker, mock_milvus):
        engine = RAGEngine(embedding=mock_embedding, reranker=mock_reranker, milvus=mock_milvus)

        scored, _ = engine.query("test query", top_k=5, hybrid=True, rerank=False)

        mock_reranker.rerank.assert_not_called()
        # Without rerank, ScoredDocuments are built from unique candidates with score=0.0
        assert all(doc.score == 0.0 for doc in scored)

    def test_query_deduplicates_candidates(self, mock_embedding, mock_reranker, mock_milvus):
        # Same doc appears in both dense and sparse results
        shared_hit = _fake_milvus_hit("dup_1", 0.9, "duplicated content")
        mock_milvus.dense_search.return_value = [shared_hit, _fake_milvus_hit("d_unique", 0.7, "unique")]
        mock_milvus.sparse_search.return_value = [shared_hit, _fake_milvus_hit("s_unique", 0.6, "sparse unique")]

        engine = RAGEngine(embedding=mock_embedding, reranker=mock_reranker, milvus=mock_milvus)
        engine.query("test", top_k=5, hybrid=True, rerank=True)

        # The reranker should receive deduplicated candidates
        rerank_call_docs = mock_reranker.rerank.call_args[0][1]
        contents = [d["content"] for d in rerank_call_docs]
        # "duplicated content" should appear only once
        assert contents.count("duplicated content") == 1

    def test_query_with_graph_returns_three_tuple(self, mock_embedding, mock_reranker, mock_milvus):
        mock_graph = MagicMock(spec=GraphStore)
        mock_graph.get_champion_synergies.return_value = [
            {"champion": "zed", "shared_traits": ["assassin"], "count": 1},
        ]

        engine = RAGEngine(
            embedding=mock_embedding, reranker=mock_reranker, milvus=mock_milvus, graph=mock_graph,
        )

        result = engine.query_with_graph("akali comp", top_k=5)

        assert isinstance(result, tuple)
        assert len(result) == 3
        scored, graph_records, total_ms = result
        assert isinstance(scored, list)
        assert isinstance(graph_records, list)
        assert isinstance(total_ms, int)
        # The reranker returns a doc with champion_id="akali", so graph should be queried
        mock_graph.get_champion_synergies.assert_called()


# ---------------------------------------------------------------------------
# TestBGEEmbedding
# ---------------------------------------------------------------------------

class TestBGEEmbedding:

    def test_encode_query_returns_dict(self):
        emb = BGEEmbedding()
        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": [[0.1, 0.2, 0.3]],
            "lexical_weights": [{5: 1.2, 100: 0.8}],
            "colbert_vecs": [[[0.1, 0.2]]],
        }
        emb._model = mock_model  # inject to skip lazy load

        result = emb.encode_query("akali build")

        assert "dense" in result
        assert "sparse" in result
        assert "colbert_vecs" in result
        # encode_query unwraps the batch dimension
        assert result["dense"] == [0.1, 0.2, 0.3]
        assert result["sparse"] == {5: 1.2, 100: 0.8}
        assert result["colbert_vecs"] == [[0.1, 0.2]]

    def test_sparse_to_milvus_converts_types(self):
        sparse = {"5": 1.2, "100": 0.8, 42: 3}

        result = BGEEmbedding.sparse_to_milvus(sparse)

        for key, value in result.items():
            assert isinstance(key, int)
            assert isinstance(value, float)
        assert result == {5: 1.2, 100: 0.8, 42: 3.0}


# ---------------------------------------------------------------------------
# TestBGEReranker
# ---------------------------------------------------------------------------

class TestBGEReranker:

    def test_rerank_returns_sorted_docs(self):
        rr = BGEReranker()
        mock_model = MagicMock()
        # Return scores in order [0.3, 0.9, 0.6] — reranker should sort descending
        mock_model.compute_score.return_value = [0.3, 0.9, 0.6]
        rr._model = mock_model

        docs = [
            {"content": "low score doc", "metadata": {"source": "a"}},
            {"content": "high score doc", "metadata": {"source": "b"}},
            {"content": "mid score doc", "metadata": {"source": "c"}},
        ]
        result = rr.rerank("query", docs)

        assert len(result) == 3
        assert result[0].score == 0.9
        assert result[0].content == "high score doc"
        assert result[1].score == 0.6
        assert result[2].score == 0.3
        # Verify descending order
        for i in range(len(result) - 1):
            assert result[i].score >= result[i + 1].score

    def test_rerank_empty_documents(self):
        rr = BGEReranker()
        result = rr.rerank("query", [])
        assert result == []

    def test_rerank_respects_top_k(self):
        rr = BGEReranker()
        mock_model = MagicMock()
        mock_model.compute_score.return_value = [0.9, 0.8, 0.7, 0.6, 0.5]
        rr._model = mock_model

        docs = [{"content": f"doc_{i}"} for i in range(5)]
        result = rr.rerank("query", docs, top_k=2)

        assert len(result) == 2
        assert result[0].score == 0.9
        assert result[1].score == 0.8


# ---------------------------------------------------------------------------
# TestGraphStore
# ---------------------------------------------------------------------------

class TestGraphStore:

    def test_run_cypher_without_connect_raises(self):
        gs = GraphStore()
        # _driver is None by default
        with pytest.raises(RuntimeError, match="not connected"):
            gs.run_cypher("MATCH (n) RETURN n")

    def test_is_healthy_returns_false_when_disconnected(self):
        gs = GraphStore()
        assert gs.is_healthy() is False

    def test_get_champion_synergies_calls_cypher(self):
        gs = GraphStore()
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [
            MagicMock(data=MagicMock(return_value={"champion": "zed", "shared_traits": ["assassin"], "count": 2})),
        ]
        # Make record.data() work properly
        record = MagicMock()
        record.data.return_value = {"champion": "zed", "shared_traits": ["assassin"], "count": 2}
        mock_session.run.return_value = [record]
        gs._driver = mock_driver

        result = gs.get_champion_synergies("akali")

        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        params = call_args[1].get("parameters") or call_args[0][1]
        assert "Champion" in cypher
        assert "HAS_TRAIT" in cypher
        assert params.get("name") == "akali" or (call_args[1].get("parameters", {}).get("name") == "akali")
        assert len(result) == 1
        assert result[0]["champion"] == "zed"
