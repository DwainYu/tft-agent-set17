"""RAG internal endpoints — /internal/rag/query and /internal/graph/query."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from api.models.rag import (
    RagQueryRequest,
    RagQueryResponse,
    RagDocument,
    GraphQueryRequest,
    GraphQueryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["rag"])

# ---------------------------------------------------------------------------
# Module-level singletons (populated on first request / at startup)
# ---------------------------------------------------------------------------
_rag_engine = None
_graph_store = None


def get_rag_engine():
    """Lazy-init the RAGEngine singleton."""
    global _rag_engine
    if _rag_engine is None:
        from api.config import get_settings
        from api.services.rag.engine import RAGEngine, MilvusStore
        from api.services.rag.embedding import BGEEmbedding
        from api.services.rag.reranker import BGEReranker
        from api.services.rag.graph_store import GraphStore

        s = get_settings()
        embedding = BGEEmbedding(
            model_name=s.EMBEDDING_MODEL,
            device=s.DEVICE,
        )
        reranker = BGEReranker(
            model_name=s.RERANKER_MODEL,
            device=s.DEVICE,
        )
        milvus = MilvusStore(host=s.MILVUS_HOST, port=s.MILVUS_PORT)
        graph = GraphStore(
            uri=s.NEO4J_URI,
            user=s.NEO4J_USER,
            password=s.NEO4J_PASSWORD,
        )
        try:
            milvus.connect()
            milvus.ensure_collection()
        except Exception as exc:
            logger.warning("Milvus not available: %s", exc)

        try:
            graph.connect()
        except Exception as exc:
            logger.warning("Neo4j not available: %s", exc)
            graph = None

        _rag_engine = RAGEngine(
            embedding=embedding,
            reranker=reranker,
            milvus=milvus,
            graph=graph,
        )
    return _rag_engine


def get_graph_store():
    """Lazy-init the GraphStore singleton."""
    global _graph_store
    if _graph_store is None:
        from api.config import get_settings
        from api.services.rag.graph_store import GraphStore

        s = get_settings()
        _graph_store = GraphStore(
            uri=s.NEO4J_URI,
            user=s.NEO4J_USER,
            password=s.NEO4J_PASSWORD,
        )
        try:
            _graph_store.connect()
        except Exception as exc:
            logger.warning("Neo4j not available: %s", exc)
    return _graph_store


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/rag/query", response_model=RagQueryResponse)
async def rag_query(req: RagQueryRequest):
    """Hybrid search + optional reranking over the TFT document store."""
    engine = get_rag_engine()
    try:
        scored, latency_ms = engine.query(
            req.query,
            top_k=req.top_k,
            hybrid=req.hybrid,
            rerank=req.rerank,
        )
    except Exception as exc:
        logger.exception("RAG query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    documents = [
        RagDocument(
            id=f"doc_{i}",
            score=doc.score,
            content=doc.content,
            metadata=doc.metadata,
        )
        for i, doc in enumerate(scored)
    ]
    return RagQueryResponse(documents=documents, latency_ms=latency_ms)


@router.post("/graph/query", response_model=GraphQueryResponse)
async def graph_query(req: GraphQueryRequest):
    """Execute a read-only Cypher query against the TFT knowledge graph."""
    import time

    store = get_graph_store()
    if store is None or not store.is_healthy():
        raise HTTPException(status_code=503, detail="Neo4j not available")

    start = time.perf_counter()
    try:
        records = store.run_cypher(req.cypher, req.params)
    except Exception as exc:
        logger.exception("Graph query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    latency_ms = int((time.perf_counter() - start) * 1000)
    return GraphQueryResponse(records=records, latency_ms=latency_ms)
