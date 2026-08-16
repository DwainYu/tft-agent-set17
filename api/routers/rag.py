"""RAG internal endpoints — /internal/rag/query and /internal/graph/query.

The engine and graph singletons are owned by the service layer
(``api.services.rag.engine`` / ``api.services.rag.graph_store``) and shared
with the agent tool layer, so models and connections are created once.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from api.models.rag import (
    RagQueryRequest,
    RagQueryResponse,
    RagDocument,
    GraphQueryRequest,
    GraphQueryResponse,
)
from api.services.rag.engine import get_rag_engine
from api.services.rag.graph_store import get_graph_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["rag"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/rag/query", response_model=RagQueryResponse)
async def rag_query(req: RagQueryRequest):
    """Hybrid search + optional reranking over the TFT document store."""
    try:
        engine = get_rag_engine()
    except Exception as exc:
        logger.warning("RAG engine unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail=f"RAG service unavailable: {exc}"
        ) from exc

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
    try:
        store = get_graph_store()
    except Exception as exc:
        logger.warning("Graph store unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Neo4j not available") from exc

    if not store.is_healthy():
        raise HTTPException(status_code=503, detail="Neo4j not available")

    start = time.perf_counter()
    try:
        records = store.run_cypher(req.cypher, req.params)
    except Exception as exc:
        logger.exception("Graph query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    latency_ms = int((time.perf_counter() - start) * 1000)
    return GraphQueryResponse(records=records, latency_ms=latency_ms)
