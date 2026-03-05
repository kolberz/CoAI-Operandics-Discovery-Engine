from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from collections import Counter

from discovery.tools.corridor import LatentState


def _get_first(stats: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    """Return the first present numeric value from stats for the given keys."""
    for k in keys:
        if k in stats:
            try:
                return float(stats[k])
            except Exception:
                pass
    return float(default)


def _counter_from_applied(md: Dict[str, Any]) -> Counter:
    """
    Expect md["applied_rules_counter"] is a dict[str,int] (your Phase 6 aggregation).
    Convert to Counter safely.
    """
    d = md.get("applied_rules_counter", {}) or {}
    if isinstance(d, Counter):
        return d
    if isinstance(d, dict):
        c = Counter()
        for k, v in d.items():
            try:
                c[str(k)] += int(v)
            except Exception:
                pass
        return c
    return Counter()


def _entropy_nats(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    H = 0.0
    for _, c in counter.items():
        if c <= 0:
            continue
        p = c / total
        H -= p * math.log(p)
    return H


def _cosine_similarity(c1: Counter, c2: Counter) -> float:
    """Cosine similarity between two nonnegative count vectors (range [0,1])."""
    if not c1 or not c2:
        return 0.0
    # dot
    dot = 0.0
    for k, v in c1.items():
        dot += float(v) * float(c2.get(k, 0))
    # norms
    n1 = math.sqrt(sum(float(v) * float(v) for v in c1.values()))
    n2 = math.sqrt(sum(float(v) * float(v) for v in c2.values()))
    if n1 <= 0 or n2 <= 0:
        return 0.0
    sim = dot / (n1 * n2)
    # clamp numerical noise
    return max(0.0, min(1.0, sim))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class DiscoveryStateAdapter:
    """
    Deterministic adapter: maps DiscoverySession to LatentState per cycle.
    Keeps minimal history for centroid similarity and progress calculation.
    """
    # weights for divergence composite
    alpha_rule_div: float = 0.7
    progress_scale_kappa: float = 3.0

    # cached previous cycle state
    prev_rule_counter: Counter = None  # type: ignore
    prev_theorem_count: int = 0

    def __post_init__(self):
        if self.prev_rule_counter is None:
            self.prev_rule_counter = Counter()

    def __call__(self, session: Any) -> LatentState:
        md: Dict[str, Any] = getattr(session, "metadata", {}) or {}
        stats: Dict[str, Any] = getattr(session, "stats", {}) or {}

        # --- Extract current counters and theorem count ---
        rule_counter = _counter_from_applied(md)
        theorem_count = len(getattr(session, "theorems", []) or [])

        # --- 1) Entropy of rule usage ---
        entropy = _entropy_nats(rule_counter)

        # --- 2) Coherence proxy via redundancy rate ---
        redundant = _get_first(stats, "redundant_skipped", "redundant", default=0.0)
        processed = _get_first(
            stats,
            "clauses_processed", "clauses_seen", "clauses_total",
            "nodes_explored", "nodes",
            default=1.0
        )
        redundancy_rate = redundant / max(1.0, processed)
        attention_coherence = _clamp01(1.0 - redundancy_rate)

        # --- 3) Search magnitude proxy ---
        clauses = _get_first(stats, "clauses_total", "clauses_seen", "clauses", default=0.0)
        nodes = _get_first(stats, "nodes_explored", "nodes", default=0.0)
        embedding_norm = math.log1p(max(0.0, clauses) + max(0.0, nodes))

        # --- 4) Similarity to previous cycle ---
        centroid_similarity = _cosine_similarity(rule_counter, self.prev_rule_counter)

        # --- 5) Progress + divergence composite ---
        delta_thm = max(0, theorem_count - self.prev_theorem_count)
        progress = 1.0 - math.exp(-float(delta_thm) / max(1e-9, self.progress_scale_kappa))  # in [0,1)
        rule_div = 1.0 - centroid_similarity  # in [0,1]
        manifold_divergence = _clamp01(self.alpha_rule_div * rule_div + (1.0 - self.alpha_rule_div) * progress)

        # Update history (deterministically)
        self.prev_rule_counter = rule_counter
        self.prev_theorem_count = theorem_count

        return LatentState(
            entropy=float(entropy),
            attention_coherence=float(attention_coherence),
            embedding_norm=float(embedding_norm),
            manifold_divergence=float(manifold_divergence),
            centroid_similarity=float(centroid_similarity),
        )
