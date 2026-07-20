"""Ragas evaluation tests (placeholder).

These tests will use the Ragas framework to evaluate the quality of the
agent's responses against the sample dataset once the LLM pipeline is
fully integrated.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.eval

# ---------------------------------------------------------------------------
# Evaluation thresholds (to be tuned after initial baseline)
# ---------------------------------------------------------------------------
FAITHFULNESS_THRESHOLD = 0.80
ANSWER_RELEVANCY_THRESHOLD = 0.75
CONTEXT_PRECISION_THRESHOLD = 0.70
CONTEXT_RECALL_THRESHOLD = 0.70

try:
    import ragas  # noqa: F401

    _ragas_available = True
except ImportError:
    _ragas_available = False


@pytest.mark.skipif(
    not _ragas_available,
    reason="Ragas not yet configured",
)
class TestRagasEvaluation:
    """Evaluate agent responses using the Ragas framework.

    Once Ragas is integrated, these tests should:
    - Load samples from datasets/samples.jsonl
    - Send each question to the /ask endpoint and collect the response
    - Score the response on faithfulness, answer relevancy, context precision/recall
    - Assert that aggregate scores exceed the defined thresholds
    """

    async def test_faithfulness_score(self):
        """Aggregate faithfulness score should exceed threshold."""
        raise NotImplementedError

    async def test_answer_relevancy_score(self):
        """Aggregate answer relevancy score should exceed threshold."""
        raise NotImplementedError

    async def test_context_precision_score(self):
        """Aggregate context precision score should exceed threshold."""
        raise NotImplementedError

    async def test_context_recall_score(self):
        """Aggregate context recall score should exceed threshold."""
        raise NotImplementedError
