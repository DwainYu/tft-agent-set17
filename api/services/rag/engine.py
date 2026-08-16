"""RAG Engine — orchestrates hybrid search, reranking, and graph traversal."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from api.services.rag.embedding import BGEEmbedding
from api.services.rag.reranker import BGEReranker, ScoredDocument
from api.services.rag.graph_store import GraphStore, get_graph_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Milvus helpers (lazy import)
# ---------------------------------------------------------------------------
_pymilvus: Any = None


def _get_pymilvus() -> Any:
    global _pymilvus
    if _pymilvus is None:
        try:
            import pymilvus as _p

            _pymilvus = _p
        except ImportError as exc:
            raise ImportError(
                "pymilvus is required for Milvus search. "
                "Install it with: pip install pymilvus"
            ) from exc
    return _pymilvus


# ---------------------------------------------------------------------------
# Internal data classes
# ---------------------------------------------------------------------------
@dataclass
class MilvusHit:
    """A single hit from a Milvus search."""

    id: str
    score: float
    content: str
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Milvus Collection Manager
# ---------------------------------------------------------------------------
class MilvusStore:
    """Manages Milvus collection lifecycle and hybrid search."""

    COLLECTION_NAME = "tft_documents_v2"
    DENSE_DIM = 1024  # BGE-M3 dense vector dimension

    def __init__(
        self,
        host: str = "localhost",
        port: str = "19530",
        collection_name: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        # Allow experiments (e.g. chunking ablations) to target a different
        # collection without touching the production one.
        self.collection_name = collection_name or self.COLLECTION_NAME
        self._connections: Any = None
        self._collection: Any = None

    def connect(self) -> None:
        pym = _get_pymilvus()
        pym.connections.connect(host=self._host, port=self._port)
        self._connections = pym.connections
        logger.info("Connected to Milvus at %s:%s", self._host, self._port)

    def is_ready(self) -> bool:
        """True once a collection has been loaded and is searchable."""
        return self._collection is not None

    def drop_collection(self) -> None:
        """Drop the collection if it exists (for idempotent re-ingestion)."""
        pym = _get_pymilvus()
        if pym.utility.has_collection(self.collection_name):
            pym.utility.drop_collection(self.collection_name)
            logger.info("Dropped existing collection '%s'", self.collection_name)
        self._collection = None

    def ensure_collection(self) -> None:
        """Create the collection + indexes if they don't exist."""
        pym = _get_pymilvus()
        from pymilvus import (
            CollectionSchema,
            FieldSchema,
            DataType,
            Collection,
        )

        if pym.utility.has_collection(self.collection_name):
            self._collection = Collection(self.collection_name)
            self._collection.load()
            return

        fields = [
            FieldSchema("id", DataType.VARCHAR, is_primary=True, max_length=256),
            FieldSchema("content", DataType.VARCHAR, max_length=65535),
            FieldSchema("dense", DataType.FLOAT_VECTOR, dim=self.DENSE_DIM),
            FieldSchema("sparse", DataType.SPARSE_FLOAT_VECTOR),
            FieldSchema("doc_type", DataType.VARCHAR, max_length=64),
            FieldSchema("champion_id", DataType.VARCHAR, max_length=64),
            # Provenance for citation/attribution
            FieldSchema("source", DataType.VARCHAR, max_length=512),
            FieldSchema("title", DataType.VARCHAR, max_length=256),
        ]
        schema = CollectionSchema(fields, description="TFT RAG document store")
        self._collection = Collection(self.collection_name, schema)

        # Dense index (HNSW)
        self._collection.create_index(
            "dense",
            {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}},
        )
        # Sparse index
        self._collection.create_index(
            "sparse",
            {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "IP"},
        )
        self._collection.load()
        logger.info("Milvus collection '%s' created", self.COLLECTION_NAME)

    def insert(self, docs: list[dict[str, Any]]) -> int:
        """Insert documents into the collection.

        Each doc must have: id, content, dense (list[float]),
        sparse (dict[int, float]). Optional metadata: doc_type, champion_id,
        source, title.
        """
        if self._collection is None:
            raise RuntimeError("Collection not initialised")

        data = [
            [d["id"] for d in docs],
            [d["content"] for d in docs],
            [d["dense"] for d in docs],
            [d["sparse"] for d in docs],
            [d.get("doc_type", "") for d in docs],
            [d.get("champion_id", "") for d in docs],
            [d.get("source", "") for d in docs],
            [d.get("title", "") for d in docs],
        ]
        self._collection.insert(data)
        self._collection.flush()
        return len(docs)

    def dense_search(
        self, vector: list[float], top_k: int = 20, filters: str = ""
    ) -> list[MilvusHit]:
        """Run a dense vector similarity search."""
        if self._collection is None:
            return []

        search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
        results = self._collection.search(
            data=[vector],
            anns_field="dense",
            param=search_params,
            limit=top_k,
            expr=filters or None,
            output_fields=["content", "doc_type", "champion_id", "source", "title"],
        )
        return [
            MilvusHit(
                id=hit.id,
                score=hit.score,
                content=hit.entity.get("content", ""),
                metadata={
                    "doc_type": hit.entity.get("doc_type", ""),
                    "champion_id": hit.entity.get("champion_id", ""),
                    "source": hit.entity.get("source", ""),
                    "title": hit.entity.get("title", ""),
                },
            )
            for hit in results[0]
        ]

    def sparse_search(
        self, vector: dict[int, float], top_k: int = 20, filters: str = ""
    ) -> list[MilvusHit]:
        """Run a sparse vector (BM25-like) search."""
        if self._collection is None:
            return []

        search_params = {"metric_type": "IP"}
        results = self._collection.search(
            data=[vector],
            anns_field="sparse",
            param=search_params,
            limit=top_k,
            expr=filters or None,
            output_fields=["content", "doc_type", "champion_id", "source", "title"],
        )
        return [
            MilvusHit(
                id=hit.id,
                score=hit.score,
                content=hit.entity.get("content", ""),
                metadata={
                    "doc_type": hit.entity.get("doc_type", ""),
                    "champion_id": hit.entity.get("champion_id", ""),
                    "source": hit.entity.get("source", ""),
                    "title": hit.entity.get("title", ""),
                },
            )
            for hit in results[0]
        ]


# ---------------------------------------------------------------------------
# RAG Engine
# ---------------------------------------------------------------------------
class RAGEngine:
    """Orchestrates the full RAG pipeline:

    1. Embed query (BGE-M3 → dense + sparse)
    2. Hybrid search (Milvus dense + sparse)
    3. Re-rank (BGE-Reranker)
    4. Optional graph traversal (Neo4j two-hop)
    """

    def __init__(
        self,
        embedding: BGEEmbedding | None = None,
        reranker: BGEReranker | None = None,
        milvus: MilvusStore | None = None,
        graph: GraphStore | None = None,
    ) -> None:
        self.embedding = embedding or BGEEmbedding()
        self.reranker = reranker or BGEReranker()
        self.milvus = milvus or MilvusStore()
        self.graph = graph

    # ------------------------------------------------------------------
    # Retrieval (candidate recall) — separated from reranking so each
    # stage can be evaluated/ablated independently.
    # ------------------------------------------------------------------
    def retrieve(
        self,
        query_text: str,
        *,
        mode: str = "hybrid",
        fetch_k: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Recall candidate documents from Milvus.

        Parameters
        ----------
        mode:
            ``"dense"`` — HNSW dense search only.
            ``"sparse"`` — inverted-index sparse search only.
            ``"hybrid"`` — both, fused with Reciprocal Rank Fusion.
        fetch_k:
            Number of candidates to recall (before any rerank truncation).

        Returns ``(candidates, latency_ms)`` where each candidate is
        ``{"content": str, "metadata": dict}`` in ranked order.
        """
        start = time.perf_counter()

        # Fast path: nothing to search if the collection is not loaded. This
        # avoids loading the (multi-GB) embedding model for an empty result.
        if not self.milvus.is_ready():
            logger.debug("Milvus collection not ready — returning empty results")
            return [], 0

        # Step 1: Encode query
        encoded = self.embedding.encode_query(query_text)

        # Step 2: Milvus search (per mode)
        if mode == "dense":
            dense_hits = self.milvus.dense_search(list(encoded["dense"]), top_k=fetch_k)
            candidates = dense_hits
        elif mode == "sparse":
            sparse_vec = BGEEmbedding.sparse_to_milvus(encoded["sparse"])
            sparse_hits = self.milvus.sparse_search(sparse_vec, top_k=fetch_k)
            candidates = sparse_hits
        elif mode == "hybrid":
            dense_hits = self.milvus.dense_search(list(encoded["dense"]), top_k=fetch_k)
            sparse_vec = BGEEmbedding.sparse_to_milvus(encoded["sparse"])
            sparse_hits = self.milvus.sparse_search(sparse_vec, top_k=fetch_k)
            candidates = self._reciprocal_rank_fusion(dense_hits, sparse_hits)
        else:
            raise ValueError(f"Unknown retrieval mode: {mode!r}")

        # Deduplicate by id, preserving ranked order
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for hit in candidates:
            if hit.id not in seen:
                seen.add(hit.id)
                unique.append({"content": hit.content, "metadata": hit.metadata})

        elapsed = int((time.perf_counter() - start) * 1000)
        return unique, elapsed

    # ------------------------------------------------------------------
    # Main query entry point
    # ------------------------------------------------------------------
    def query(
        self,
        query_text: str,
        *,
        top_k: int = 5,
        hybrid: bool = True,
        rerank: bool = True,
    ) -> tuple[list[ScoredDocument], int]:
        """Run the full RAG pipeline.

        Returns ``(scored_documents, latency_ms)``.
        """
        start = time.perf_counter()

        # Step 1+2: candidate recall (dense/sparse/hybrid)
        mode = "hybrid" if hybrid else "dense"
        unique, _ = self.retrieve(query_text, mode=mode, fetch_k=top_k * 4)

        # Step 3: Rerank. If the reranker is unavailable (model not vendored /
        # download blocked), degrade to the RRF-fused order instead of failing
        # the whole query — retrieval results are still valuable unranked.
        if rerank and unique:
            try:
                scored = self.reranker.rerank(query_text, unique, top_k=top_k)
            except Exception as exc:
                logger.warning(
                    "Reranker unavailable (%s); returning RRF-ordered results", exc
                )
                scored = [
                    ScoredDocument(
                        content=c["content"],
                        score=0.0,
                        metadata=c.get("metadata", {}),
                    )
                    for c in unique[:top_k]
                ]
        else:
            scored = [
                ScoredDocument(
                    content=c["content"],
                    score=0.0,
                    metadata=c.get("metadata", {}),
                )
                for c in unique[:top_k]
            ]

        elapsed = int((time.perf_counter() - start) * 1000)
        return scored, elapsed

    # ------------------------------------------------------------------
    # Graph-augmented retrieval
    # ------------------------------------------------------------------
    def query_with_graph(
        self,
        query_text: str,
        *,
        top_k: int = 5,
    ) -> tuple[list[ScoredDocument], list[dict], int]:
        """RAG query + Neo4j two-hop reasoning.

        Returns ``(scored_documents, graph_records, latency_ms)``.
        """
        scored, rag_ms = self.query(query_text, top_k=top_k)

        graph_records: list[dict] = []
        graph_ms = 0
        if self.graph is not None:
            g_start = time.perf_counter()
            # Extract champion names from scored results for graph lookup
            for doc in scored:
                champ = doc.metadata.get("champion_id", "")
                if champ:
                    records = self.graph.get_champion_synergies(champ)
                    graph_records.extend(records)
            graph_ms = int((time.perf_counter() - g_start) * 1000)

        return scored, graph_records, rag_ms + graph_ms

    # ------------------------------------------------------------------
    # Fusion helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _reciprocal_rank_fusion(
        *hit_lists: list[MilvusHit],
        k: int = 60,
    ) -> list[MilvusHit]:
        """Reciprocal Rank Fusion (RRF) across multiple ranked lists.

        Score = sum(1 / (k + rank)) for each list where the doc appears.
        """
        scores: dict[str, float] = {}
        meta: dict[str, MilvusHit] = {}

        for hits in hit_lists:
            for rank, hit in enumerate(hits):
                scores[hit.id] = scores.get(hit.id, 0.0) + 1.0 / (k + rank + 1)
                if hit.id not in meta:
                    meta[hit.id] = hit

        ranked_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        result: list[MilvusHit] = []
        for doc_id in ranked_ids:
            hit = meta[doc_id]
            result.append(
                MilvusHit(
                    id=hit.id,
                    score=scores[doc_id],
                    content=hit.content,
                    metadata=hit.metadata,
                )
            )
        return result


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_rag_engine() -> RAGEngine:
    """Process-level singleton RAG engine assembled from ``api.config``.

    This is the single source of truth for the RAG engine — both the agent
    tool layer (``api.agent.tools``) and the internal HTTP endpoints
    (``api.routers.rag``) reuse it, so the BGE-M3 / reranker models and the
    Milvus connection are created exactly once per process.

    Behaviour notes:
    * Milvus is **required** for retrieval, so its connection error is allowed
      to propagate.  ``lru_cache`` does not cache exceptions, which means a
      failed connect is retried on the next call (Milvus can come up without
      restarting the process).
    * The Neo4j graph is an **optional** enhancement; if it is unreachable we
      degrade to ``graph=None`` and keep pure vector retrieval working.
    * Model weights are still lazily loaded inside BGEEmbedding/BGEReranker on
      first ``encode``, so building this engine is cheap even if RAG is never
      actually queried.
    """
    from api.config import get_settings

    s = get_settings()
    embedding = BGEEmbedding(
        model_name=s.EMBEDDING_MODEL, device=s.DEVICE, use_fp16=s.USE_FP16
    )
    reranker = BGEReranker(
        model_name=s.RERANKER_MODEL, device=s.DEVICE, use_fp16=s.USE_FP16
    )

    # Required: connect + ensure collection. Raises if Milvus is down.
    milvus = MilvusStore(host=s.MILVUS_HOST, port=s.MILVUS_PORT)
    milvus.connect()
    milvus.ensure_collection()

    # Optional: graph augmentation. Degrade to None if Neo4j is down.
    try:
        graph = get_graph_store()
    except Exception as exc:
        logger.warning("Neo4j unavailable, graph augmentation disabled: %s", exc)
        graph = None

    return RAGEngine(
        embedding=embedding,
        reranker=reranker,
        milvus=milvus,
        graph=graph,
    )
