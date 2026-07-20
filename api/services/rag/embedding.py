"""BGE-M3 embedding wrapper — dense, sparse & multi-vector encoding."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import so the module can be imported even when FlagEmbedding is not
# installed (e.g. during unit tests with mocks).
# ---------------------------------------------------------------------------
_FlagModel: type | None = None


def _get_flag_model_class() -> type:
    global _FlagModel
    if _FlagModel is None:
        try:
            from FlagEmbedding import BGEM3FlagModel

            _FlagModel = BGEM3FlagModel
        except ImportError as exc:
            raise ImportError(
                "FlagEmbedding is required for BGEEmbedding. "
                "Install it with: pip install FlagEmbedding"
            ) from exc
    return _FlagModel


class BGEEmbedding:
    """Thin wrapper around the BGE-M3 model for encoding text.

    Produces three representations per input:
    * **dense** — 1024-dim float vector
    * **sparse** — dict[int, float] lexical weights (for BM25-like retrieval)
    * **colbert** — list[list[float]] multi-vector (late interaction)
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = "cpu",
        use_fp16: bool = False,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._use_fp16 = use_fp16
        self._model: Any = None

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------
    def _ensure_model(self) -> None:
        if self._model is None:
            cls = _get_flag_model_class()
            logger.info("Loading BGE-M3 model %s on %s", self._model_name, self._device)
            self._model = cls(
                self._model_name,
                use_fp16=self._use_fp16,
                device=self._device,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int = 32,
        max_length: int = 8192,
    ) -> dict[str, Any]:
        """Encode a batch of texts.

        Returns a dict with keys ``dense``, ``sparse``, ``colbert_vecs``.
        """
        self._ensure_model()
        output = self._model.encode(
            texts,
            batch_size=batch_size,
            max_length=max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=True,
        )
        return {
            "dense": output["dense_vecs"],
            "sparse": output["lexical_weights"],
            "colbert_vecs": output["colbert_vecs"],
        }

    def encode_query(self, query: str) -> dict[str, Any]:
        """Convenience: encode a single query string."""
        result = self.encode([query])
        return {
            "dense": result["dense"][0],
            "sparse": result["sparse"][0],
            "colbert_vecs": result["colbert_vecs"][0],
        }

    # ------------------------------------------------------------------
    # Serialization helpers for Milvus
    # ------------------------------------------------------------------
    @staticmethod
    def sparse_to_milvus(sparse: dict[int, float]) -> dict[int, float]:
        """Convert FlagEmbedding sparse output to Milvus sparse vector format."""
        return {int(k): float(v) for k, v in sparse.items()}
