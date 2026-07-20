"""BGE-Reranker wrapper — cross-encoder re-ranking for retrieved documents."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_FlagReranker: type | None = None


def _get_reranker_class() -> type:
    global _FlagReranker
    if _FlagReranker is None:
        try:
            from FlagEmbedding import FlagReranker

            _FlagReranker = FlagReranker
        except ImportError as exc:
            raise ImportError(
                "FlagEmbedding is required for BGEReranker. "
                "Install it with: pip install FlagEmbedding"
            ) from exc
    return _FlagReranker


@dataclass
class ScoredDocument:
    """A document paired with its reranker relevance score."""

    content: str
    score: float
    metadata: dict[str, Any]


class BGEReranker:
    """Cross-encoder reranker based on BGE-Reranker-v2-m3.

    Given a query and a list of candidate documents, produces relevance
    scores that can be used to re-sort the candidates.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        use_fp16: bool = False,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._use_fp16 = use_fp16
        self._model: Any = None

    def _ensure_model(self) -> None:
        if self._model is None:
            cls = _get_reranker_class()
            logger.info("Loading reranker model %s on %s", self._model_name, self._device)
            self._model = cls(
                self._model_name,
                use_fp16=self._use_fp16,
                device=self._device,
            )

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        *,
        top_k: int | None = None,
        batch_size: int = 32,
    ) -> list[ScoredDocument]:
        """Score and re-sort *documents* by relevance to *query*.

        Each element in *documents* must have a ``content`` key and may
        optionally carry ``metadata``.

        Returns a list of :class:`ScoredDocument` sorted by descending score.
        """
        if not documents:
            return []

        self._ensure_model()

        pairs: list[list[str]] = [[query, doc["content"]] for doc in documents]
        scores = self._model.compute_score(pairs, normalize=True, batch_size=batch_size)

        # compute_score returns a single float when len(pairs)==1
        if isinstance(scores, float):
            scores = [scores]

        scored = [
            ScoredDocument(
                content=doc["content"],
                score=float(s),
                metadata=doc.get("metadata", {}),
            )
            for doc, s in zip(documents, scores)
        ]
        scored.sort(key=lambda d: d.score, reverse=True)

        if top_k is not None:
            scored = scored[:top_k]

        return scored
