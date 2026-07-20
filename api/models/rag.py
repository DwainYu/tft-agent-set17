"""Pydantic models for RAG request / response."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    """Request body for ``POST /internal/rag/query``."""

    query: str = Field(..., min_length=1, description="Natural-language query")
    top_k: int = Field(default=5, ge=1, le=50)
    hybrid: bool = Field(default=True, description="Use hybrid (dense + sparse) search")
    rerank: bool = Field(default=True, description="Re-rank results with cross-encoder")


class RagDocument(BaseModel):
    """A single retrieved document."""

    id: str
    score: float
    content: str
    metadata: dict = Field(default_factory=dict)


class RagQueryResponse(BaseModel):
    """Response body for ``POST /internal/rag/query``."""

    documents: list[RagDocument]
    latency_ms: int


class GraphQueryRequest(BaseModel):
    """Request body for ``POST /internal/graph/query``."""

    cypher: str = Field(..., min_length=1)
    params: dict = Field(default_factory=dict)


class GraphQueryResponse(BaseModel):
    """Response body for ``POST /internal/graph/query``."""

    records: list[dict]
    latency_ms: int
