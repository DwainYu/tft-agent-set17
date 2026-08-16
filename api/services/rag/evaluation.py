"""Retrieval evaluation harness — ground-truth based, single-pass metrics.

Design goals
------------
1. **Single pass**: each query is executed exactly once per configuration;
   all metrics (Hit@k, MRR, Precision@k, entity recall, latency) are derived
   from the same ranked result list.  This keeps ablation runs fast and makes
   metrics directly comparable.
2. **Ground-truth relevance**: instead of naive keyword intersection, a
   document is relevant when it is *about* one of the annotated entities:
   exact ``champion_id`` metadata match, or the entity's Chinese name found
   in content / title / source (with boundary guards for 1-char names such
   as "易", which must not match "容易"/"交易").
3. **Empty-ground-truth queries** (version meta, generic economy tips) are
   judged by ``doc_type == "meta_overview"`` — the corpus document class
   actually written to answer them.

Used by ``scripts/eval/run_ablation.py`` (ablation experiments) and by the
live mode of ``tests/eval/test_ragas_retrieval.py``.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from api.services.rag.engine import RAGEngine

logger = logging.getLogger(__name__)

# CJK Unified Ideographs range — used for name-boundary assertions.
_CJK = r"\u4e00-\u9fff"


# ---------------------------------------------------------------------------
# Ground truth (entity id → Chinese name)
# ---------------------------------------------------------------------------
class GroundTruth:
    """Champion / trait name index loaded from ``tft.db``.

    Provides boundary-safe matching: names of length 1 (e.g. "易") only match
    when not surrounded by other CJK characters, preventing substring false
    positives such as "容易" or "交易".
    """

    def __init__(self, db_path: str | Path = "data/tft.db") -> None:
        self.champion_names: dict[str, str] = {}
        self.trait_names: dict[str, str] = {}
        self._patterns: dict[str, re.Pattern[str]] = {}

        conn = sqlite3.connect(str(db_path))
        try:
            for cid, name in conn.execute("SELECT id, name_zh FROM champions"):
                if name:
                    self.champion_names[cid] = name
            for tid, name in conn.execute("SELECT id, name_zh FROM traits"):
                if name:
                    self.trait_names[tid] = name
        finally:
            conn.close()

    def name_pattern(self, name: str) -> re.Pattern[str]:
        """Regex matching *name* as a standalone term.

        1-char names require non-CJK (or string) boundaries on both sides;
        longer names match as plain substrings (they are distinctive enough
        in this domain corpus).
        """
        cached = self._patterns.get(name)
        if cached is None:
            if len(name) <= 1:
                cached = re.compile(f"(?<![{_CJK}]){re.escape(name)}(?![{_CJK}])")
            else:
                cached = re.compile(re.escape(name))
            self._patterns[name] = cached
        return cached

    def contains_name(self, text: str, name: str) -> bool:
        return self.name_pattern(name).search(text) is not None


# ---------------------------------------------------------------------------
# Evaluation samples
# ---------------------------------------------------------------------------
@dataclass
class EvalSample:
    """One golden query with its annotated ground-truth entities."""

    query: str
    expected_champions: list[str] = field(default_factory=list)
    expected_traits: list[str] = field(default_factory=list)
    category: str = ""

    @property
    def has_entities(self) -> bool:
        return bool(self.expected_champions or self.expected_traits)


def load_eval_samples(path: str | Path, limit: int | None = None) -> list[EvalSample]:
    """Load golden samples from a JSONL file."""
    samples: list[EvalSample] = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            rec = json.loads(raw)
            samples.append(
                EvalSample(
                    query=rec["query"],
                    expected_champions=rec.get("expected_champions", []),
                    expected_traits=rec.get("expected_traits", []),
                    category=rec.get("category", ""),
                )
            )
            if limit and len(samples) >= limit:
                break
    return samples


# ---------------------------------------------------------------------------
# Relevance judgement
# ---------------------------------------------------------------------------
def _doc_searchable_text(candidate: dict[str, Any]) -> str:
    """Concatenate everything a relevance check may inspect."""
    meta = candidate.get("metadata", {})
    return " ".join(
        str(x)
        for x in (
            candidate.get("content", ""),
            meta.get("title", ""),
            meta.get("source", ""),
        )
        if x
    )


def is_doc_relevant(
    candidate: dict[str, Any],
    sample: EvalSample,
    gt: GroundTruth,
) -> bool:
    """Decide whether *candidate* satisfies the information need of *sample*.

    OR semantics across entities: a document about any expected champion or
    trait is relevant (e.g. for "劫主C出装" both 劫's profile and 劫's trait
    guide satisfy the need).

    Samples without annotated entities (version-meta style questions) are
    satisfied by ``meta_overview`` documents.
    """
    meta = candidate.get("metadata", {})

    if not sample.has_entities:
        return meta.get("doc_type", "") == "meta_overview"

    text = _doc_searchable_text(candidate)

    for cid in sample.expected_champions:
        if meta.get("champion_id") == cid:
            return True
        name = gt.champion_names.get(cid)
        if name and gt.contains_name(text, name):
            return True

    for tid in sample.expected_traits:
        name = gt.trait_names.get(tid)
        if name and gt.contains_name(text, name):
            return True

    return False


def _entity_is_covered(
    entity_id: str,
    kind: str,
    docs: list[dict[str, Any]],
    gt: GroundTruth,
) -> bool:
    """True when any of *docs* mentions the entity (metadata or text)."""
    names = gt.champion_names if kind == "champion" else gt.trait_names
    name = names.get(entity_id, "")
    for doc in docs:
        meta = doc.get("metadata", {})
        if kind == "champion" and meta.get("champion_id") == entity_id:
            return True
        if name and gt.contains_name(_doc_searchable_text(doc), name):
            return True
    return False


# ---------------------------------------------------------------------------
# Metric container
# ---------------------------------------------------------------------------
@dataclass
class EvalResult:
    """Aggregated retrieval metrics for one configuration."""

    config: str
    n_queries: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    precision_at_5: float
    entity_recall_at_5: float
    latency_p50_ms: float
    latency_p99_ms: float
    per_category: dict[str, dict[str, float]] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        """Flat dict for tabulation."""
        return {
            "config": self.config,
            "n": self.n_queries,
            "Hit@1": round(self.hit_at_1, 4),
            "Hit@3": round(self.hit_at_3, 4),
            "Hit@5": round(self.hit_at_5, 4),
            "MRR": round(self.mrr, 4),
            "P@5": round(self.precision_at_5, 4),
            "EntityRecall@5": round(self.entity_recall_at_5, 4),
            "P50(ms)": round(self.latency_p50_ms, 1),
            "P99(ms)": round(self.latency_p99_ms, 1),
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, int(len(sorted_values) * pct) - 1))
    return sorted_values[idx]


# ---------------------------------------------------------------------------
# Single-pass evaluator
# ---------------------------------------------------------------------------
def evaluate_config(
    samples: list[EvalSample],
    gt: GroundTruth,
    engine: RAGEngine,
    *,
    config: str,
    mode: str = "hybrid",
    rerank: bool = True,
    top_k: int = 5,
    fetch_k: int = 20,
) -> EvalResult:
    """Run every sample once through the given pipeline configuration.

    The ranked top-``top_k`` list produced for each query is scored on all
    metrics, so one retrieval pass yields everything — no repeated queries.
    """
    hits = {1: 0, 3: 0, 5: 0}
    reciprocal_ranks: list[float] = []
    precisions: list[float] = []
    entity_recalls: list[float] = []
    latencies_ms: list[float] = []
    per_category_hits: dict[str, list[float]] = {}
    per_category_rr: dict[str, list[float]] = {}

    for sample in samples:
        start = time.perf_counter()

        candidates, _ = engine.retrieve(sample.query, mode=mode, fetch_k=fetch_k)

        if rerank and candidates:
            try:
                scored = engine.reranker.rerank(sample.query, candidates, top_k=top_k)
                ranked: list[dict[str, Any]] = [
                    {"content": d.content, "metadata": d.metadata} for d in scored
                ]
            except Exception as exc:
                logger.warning(
                    "Reranker unavailable (%s); scoring recall order for %r",
                    exc,
                    sample.query,
                )
                ranked = candidates[:top_k]
        else:
            ranked = candidates[:top_k]

        latencies_ms.append((time.perf_counter() - start) * 1000)

        # Relevance flags per rank
        flags = [is_doc_relevant(doc, sample, gt) for doc in ranked]

        first_rank = next((i + 1 for i, ok in enumerate(flags) if ok), None)
        rr = 1.0 / first_rank if first_rank else 0.0
        reciprocal_ranks.append(rr)
        precisions.append(sum(flags) / top_k if top_k else 0.0)

        for k in hits:
            if any(flags[:k]):
                hits[k] += 1

        cat = sample.category or "unknown"
        per_category_hits.setdefault(cat, []).append(1.0 if any(flags[:5]) else 0.0)
        per_category_rr.setdefault(cat, []).append(rr)

        # Entity coverage across the top-k window
        if sample.has_entities:
            expected = [
                (cid, "champion") for cid in sample.expected_champions
            ] + [(tid, "trait") for tid in sample.expected_traits]
            covered = sum(
                1 for eid, kind in expected if _entity_is_covered(eid, kind, ranked, gt)
            )
            entity_recalls.append(covered / len(expected))
        else:
            entity_recalls.append(1.0)

    n = len(samples)
    latencies_ms.sort()
    per_category: dict[str, dict[str, float]] = {}
    for cat in per_category_hits:
        cat_hits = per_category_hits[cat]
        cat_rr = per_category_rr[cat]
        per_category[cat] = {
            "n": len(cat_hits),
            "hit@5": sum(cat_hits) / len(cat_hits),
            "mrr": sum(cat_rr) / len(cat_rr),
        }

    return EvalResult(
        config=config,
        n_queries=n,
        hit_at_1=hits[1] / n,
        hit_at_3=hits[3] / n,
        hit_at_5=hits[5] / n,
        mrr=sum(reciprocal_ranks) / n,
        precision_at_5=sum(precisions) / n,
        entity_recall_at_5=sum(entity_recalls) / n,
        latency_p50_ms=_percentile(latencies_ms, 0.50),
        latency_p99_ms=_percentile(latencies_ms, 0.99),
        per_category=per_category,
    )


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------
def results_to_markdown(results: list[EvalResult], title: str) -> str:
    """Render a list of EvalResult as a Markdown comparison table."""
    lines = [f"| 配置 | Hit@1 | Hit@3 | Hit@5 | MRR | P@5 | 实体召回@5 | P50(ms) | P99(ms) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        row = r.as_row()
        lines.append(
            f"| {row['config']} | {row['Hit@1']:.3f} | {row['Hit@3']:.3f} | "
            f"{row['Hit@5']:.3f} | {row['MRR']:.3f} | {row['P@5']:.3f} | "
            f"{row['EntityRecall@5']:.3f} | {row['P50(ms)']:.0f} | {row['P99(ms)']:.0f} |"
        )
    return f"**{title}**\n\n" + "\n".join(lines)
