"""
build270_merged_spec.py  — Build 2.7.0 (cleanup-complete)

A) ForwardChainingSaturator (Given Clause Loop)
B) InterestingnessScorer (Reporting/Admission, not search bias)
C) discover_and_verify_conjectures (outer science loop scaffold)
D) L0 telemetry bus + anomaly detection

Hardening:
- slots=True with field(init=False, default_factory=...) for internal state.
- Deterministic Active iteration via admission-order list + index iteration.
- Hard-stop: once max_generated reached, stop immediately (no overshoot).
- Canonicalization at single choke-point: _push_passive().
- Provenance parents are index-based (ints), not clause references.
- Axioms NOT surfaced as discoveries.
- No O(n) slicing per given-step (iterate by index).

Python: 3.10+  |  Dependencies: stdlib only.
"""

from __future__ import annotations

import heapq
import itertools
import random
import sys
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Hashable,
    Iterable,
    Iterator,
    Protocol,
    TypeVar,
    Generic,
)

# =============================================================================
# §1 — Protocols
# =============================================================================

ClauseT = TypeVar("ClauseT", bound=Hashable)
FormulaT = TypeVar("FormulaT")


class ClauseOps(Protocol[ClauseT, FormulaT]):
    """
    Pluggable operations for the saturator.

    Resolution contract:
      resolve(a, b) must be complete for the unordered pair {a, b}.
      The saturator calls resolve(given, other) only — never the reverse.

    Canonicalization:
      canonicalize() is called ONLY in _push_passive().
      All Passive/Active clauses are canonical by construction.
    """

    def canonicalize(self, c: ClauseT) -> ClauseT: ...
    def weight(self, c: ClauseT) -> int: ...
    def resolve(self, a: ClauseT, b: ClauseT) -> Iterable[ClauseT]: ...
    def redundant(self, c: ClauseT, *, active: set[ClauseT]) -> bool: ...
    def admissible(self, c: ClauseT, *, depth: int) -> bool: ...
    def to_formula(self, c: ClauseT) -> FormulaT: ...


# =============================================================================
# §2 — Interestingness scoring (reporting filter, NOT search bias)
# =============================================================================

@dataclass(frozen=True, slots=True)
class InterestingnessWeights:
    novelty: float = 0.30
    reduction: float = 0.25
    complexity_goldilocks: float = 0.20
    compositional: float = 0.20
    symmetric: float = 0.15
    associative: float = 0.15
    trivial_bonus: float = 0.10
    trivial_penalty: float = -0.50


@dataclass(frozen=True, slots=True)
class InterestingnessContext:
    max_symbols: int = 50
    compositional_symbols: frozenset[str] = frozenset(
        {
            "Seq", "Par", "Par_Dyn", "Barrier",
            "compose", "risk", "Risk", "guarantee",
            "Cost", "ResourceCost", "Comp", "Ent",
            "ID_M", "P_TRUE",
        }
    )


class FormulaIntrospection(Protocol[FormulaT]):
    """Hooks the scorer uses to inspect formulas structurally."""
    def symbols(self, f: FormulaT) -> set[str]: ...
    def complexity(self, f: FormulaT) -> int: ...
    def is_reduction(self, f: FormulaT) -> bool: ...
    def is_symmetric(self, f: FormulaT) -> bool: ...
    def is_associative(self, f: FormulaT) -> bool: ...
    def is_trivial_identity(self, f: FormulaT) -> bool: ...


@dataclass(slots=True)
class InterestingnessScorer(Generic[FormulaT]):
    """
    Reporting/admission scorer.  Does NOT bias saturation search order.
    Weights do not need to sum to 1.0; score is clamped to [0, 1].
    """
    hooks: FormulaIntrospection[FormulaT]
    weights: InterestingnessWeights = field(default_factory=InterestingnessWeights)
    min_interestingness: float = 0.30

    def score(self, f: FormulaT, ctx: InterestingnessContext) -> float:
        w = self.weights
        syms = self.hooks.symbols(f)

        novelty = min(1.0, len(syms) / max(1, ctx.max_symbols))
        reduction = 1.0 if self.hooks.is_reduction(f) else 0.0

        comp = self.hooks.complexity(f)
        complexity_goldilocks = 1.0 if (3 <= comp <= 8) else 0.0

        compositional = 1.0 if (syms & set(ctx.compositional_symbols)) else 0.0
        symmetric = 1.0 if self.hooks.is_symmetric(f) else 0.0
        associative = 1.0 if self.hooks.is_associative(f) else 0.0

        trivial_term = w.trivial_penalty if self.hooks.is_trivial_identity(f) else w.trivial_bonus

        raw = (
            w.novelty * novelty
            + w.reduction * reduction
            + w.complexity_goldilocks * complexity_goldilocks
            + w.compositional * compositional
            + w.symmetric * symmetric
            + w.associative * associative
            + trivial_term
        )
        return max(0.0, min(1.0, raw))

    def admit(self, f: FormulaT, ctx: InterestingnessContext) -> bool:
        return self.score(f, ctx) >= self.min_interestingness


# =============================================================================
# §3 — Discovery artifacts
# =============================================================================

@dataclass(frozen=True, slots=True)
class DiscoveredTheorem(Generic[FormulaT]):
    formula: FormulaT
    score: float
    tags: tuple[str, ...]
    provenance: Any


@dataclass(slots=True)
class DiscoverySession(Generic[FormulaT]):
    theorems: list[DiscoveredTheorem[FormulaT]] = field(default_factory=list)

    def add(self, thm: DiscoveredTheorem[FormulaT]) -> None:
        self.theorems.append(thm)


# =============================================================================
# §4 — Forward Chaining Saturator (Given-Clause Loop)
# =============================================================================

@dataclass(frozen=True, slots=True)
class ClauseProvenance:
    """Parents are Active indices (ints), not clause objects."""
    kind: str  # "axiom" | "resolvent"
    parents: tuple[int, int] | tuple[()] = ()
    rule: str = "resolve"
    depth: int = 0


@dataclass(frozen=True, slots=True)
class SaturationLimits:
    max_depth: int = 25
    max_active: int = 50_000
    max_passive: int = 200_000
    max_generated: int = 1_000_000
    max_given_steps: int = 500_000


@dataclass(slots=True)
class SaturationStats:
    given_steps: int = 0
    generated: int = 0
    admitted_passive: int = 0
    admitted_active: int = 0
    redundant_skipped: int = 0


@dataclass(slots=True)
class ForwardChainingSaturator(Generic[ClauseT, FormulaT]):
    """
    Given-clause loop saturator.

    Determinism: Passive via (weight, counter); Active via admission-order list.
    Canonicalization: single choke-point in _push_passive().
    Hard-stop: max_generated enforced at both loop levels.
    """

    ops: ClauseOps[ClauseT, FormulaT]
    limits: SaturationLimits = field(default_factory=SaturationLimits)

    scorer: InterestingnessScorer[FormulaT] | None = None
    score_ctx: InterestingnessContext = field(default_factory=InterestingnessContext)
    session: DiscoverySession[FormulaT] | None = None

    on_new_clause: Callable[[ClauseT, ClauseProvenance], None] | None = None

    # Internal state — declared for slots safety
    _active_set: set[ClauseT] = field(init=False, default_factory=set)
    _active_list: list[ClauseT] = field(init=False, default_factory=list)
    _active_prov: list[ClauseProvenance] = field(init=False, default_factory=list)

    _passive: list[tuple[int, int, ClauseT, ClauseProvenance]] = field(
        init=False, default_factory=list
    )
    _counter: itertools.count = field(init=False, default_factory=itertools.count)

    stats: SaturationStats = field(init=False, default_factory=SaturationStats)

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = DiscoverySession()

    @property
    def active(self) -> set[ClauseT]:
        return self._active_set

    def push_axioms(self, axioms: Iterable[ClauseT]) -> None:
        """Push axioms to Passive.  Call before run()."""
        for a in axioms:
            prov = ClauseProvenance(kind="axiom", parents=(), depth=0)
            self._push_passive(a, prov)

    def _push_passive(self, c: ClauseT, prov: ClauseProvenance) -> None:
        c = self.ops.canonicalize(c)  # single canonical gate

        if prov.depth > self.limits.max_depth:
            return
        if self.stats.generated >= self.limits.max_generated:
            return
        if len(self._passive) >= self.limits.max_passive:
            return

        w = self.ops.weight(c)
        heapq.heappush(self._passive, (w, next(self._counter), c, prov))
        self.stats.admitted_passive += 1

        if self.on_new_clause is not None:
            self.on_new_clause(c, prov)

        # Surface non-axioms only
        if prov.kind != "axiom" and self.scorer is not None and self.session is not None:
            f = self.ops.to_formula(c)
            score = self.scorer.score(f, self.score_ctx)
            if score >= self.scorer.min_interestingness:
                self.session.add(
                    DiscoveredTheorem(
                        formula=f, score=score,
                        tags=(prov.kind, prov.rule),
                        provenance=prov,
                    )
                )

    def run(self) -> Iterator[ClauseT]:
        while self._passive and self.stats.given_steps < self.limits.max_given_steps:
            if self.stats.generated >= self.limits.max_generated:
                return

            _w, _n, given, prov = heapq.heappop(self._passive)
            self.stats.given_steps += 1

            if self.ops.redundant(given, active=self._active_set):
                self.stats.redundant_skipped += 1
                continue

            if len(self._active_set) >= self.limits.max_active:
                return

            n_before = len(self._active_list)
            given_idx = n_before

            self._active_set.add(given)
            self._active_list.append(given)
            self._active_prov.append(prov)
            self.stats.admitted_active += 1
            yield given

            for i in range(n_before):
                if self.stats.generated >= self.limits.max_generated:
                    return

                other = self._active_list[i]
                other_prov = self._active_prov[i]

                for res in self.ops.resolve(given, other):
                    self.stats.generated += 1
                    if self.stats.generated >= self.limits.max_generated:
                        return

                    depth = max(prov.depth, other_prov.depth) + 1
                    if depth > self.limits.max_depth:
                        continue
                    if not self.ops.admissible(res, depth=depth):
                        continue

                    rprov = ClauseProvenance(
                        kind="resolvent",
                        parents=(given_idx, i),
                        rule="resolve",
                        depth=depth,
                    )
                    self._push_passive(res, rprov)

    def discovered_theorems(self) -> list[DiscoveredTheorem[FormulaT]]:
        assert self.session is not None
        return list(self.session.theorems)

    def build_provenance_graph(self) -> dict[int, tuple[int, int]]:
        """
        { active_idx: (parent_i, parent_j) } for resolvents only.
        Axiom indices appear as parent values but not as keys.
        """
        out: dict[int, tuple[int, int]] = {}
        for idx, p in enumerate(self._active_prov):
            if p.kind == "resolvent":
                assert isinstance(p.parents, tuple) and len(p.parents) == 2
                out[idx] = (p.parents[0], p.parents[1])
        return out


# =============================================================================
# §5 — Outer loop scaffold
# =============================================================================

class GeneralProver(Protocol[FormulaT]):
    def prove(self, conjecture: FormulaT) -> bool: ...


def discover_and_verify_conjectures(
    *,
    run_saturation: Callable[[], Iterable[DiscoveredTheorem[FormulaT]]],
    generalize: Callable[[DiscoveredTheorem[FormulaT]], Iterable[FormulaT]],
    prover: GeneralProver[FormulaT],
    promote: Callable[[FormulaT], None],
    top_k: int = 50,
) -> None:
    theorems = list(run_saturation())
    theorems.sort(key=lambda t: t.score, reverse=True)
    for thm in theorems[:top_k]:
        for conj in generalize(thm):
            if prover.prove(conj):
                promote(conj)


# =============================================================================
# §6 — Telemetry schemas
# =============================================================================

@dataclass(frozen=True, slots=True)
class InfoTheoryMetrics:
    candidate_entropy: float
    kl_divergence_from_prior: float
    mutual_info_with_context: float

@dataclass(frozen=True, slots=True)
class UncertaintyMetrics:
    epistemic_uncertainty: float
    aleatoric_uncertainty: float
    training_distribution_distance: float

@dataclass(frozen=True, slots=True)
class ReasoningMetrics:
    reasoning_chain_depth: int
    contradiction_detected_count: int
    backtracking_frequency: float
    logical_validity_score: float

@dataclass(frozen=True, slots=True)
class TopologyMetrics:
    attention_graph_density: float
    information_flow_bottlenecks: tuple[int, ...]
    attention_hub_count: int

@dataclass(frozen=True, slots=True)
class ContextMetrics:
    context_coverage_ratio: float
    retrieval_vs_generation_ratio: float
    cross_attention_concentration: float

@dataclass(frozen=True, slots=True)
class GroundingMetrics:
    grounding_confidence: float
    ungrounded_statement_ratio: float


# =============================================================================
# §7 — Trace channel registry + L0 anomaly detection
# =============================================================================

ChannelName = str


@dataclass(slots=True)
class TraceChannelRegistry:
    _channels: dict[ChannelName, Any] = field(
        init=False,
        default_factory=lambda: {
            "InfoTheory": None, "Uncertainty": None, "Reasoning": None,
            "Topology": None, "Context": None, "Grounding": None,
        },
    )

    def publish(self, channel_name: ChannelName, payload: Any) -> None:
        if channel_name not in self._channels:
            raise KeyError(f"Unknown telemetry channel: {channel_name}")
        self._channels[channel_name] = payload

    def get(self, channel_name: ChannelName) -> Any:
        return self._channels.get(channel_name)

    def flush(self) -> None:
        for k in self._channels:
            self._channels[k] = None

    def snapshot(self) -> dict[ChannelName, Any]:
        return dict(self._channels)


class AnomalyDetectedException(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class L0Thresholds:
    hallucination_risk_max: float = 0.70
    off_manifold_distance_min: float = 0.80
    logical_validity_min: float = 0.40
    grounding_confidence_min: float = 0.50
    retrieval_ratio_min: float = 0.20
    attention_density_min: float = 0.10
    bottleneck_count_max: int = 3
    backtracking_freq_max: float = 0.80
    contradiction_count_max: int = 2


@dataclass(slots=True)
class L0MetricAggregator:
    registry: TraceChannelRegistry
    thresholds: L0Thresholds = field(default_factory=L0Thresholds)
    enabled: bool = True

    def analyze_pre_thought_cloud(self) -> bool:
        if not self.enabled:
            return True

        info = self.registry.get("InfoTheory")
        unc = self.registry.get("Uncertainty")
        rsn = self.registry.get("Reasoning")
        top = self.registry.get("Topology")
        ctx = self.registry.get("Context")
        grd = self.registry.get("Grounding")

        if info is None or unc is None or rsn is None or top is None or ctx is None or grd is None:
            raise AnomalyDetectedException("INCOMPLETE_TELEMETRY: Missing channel data.")

        if not isinstance(info, InfoTheoryMetrics):
            raise AnomalyDetectedException("TYPE_MISMATCH: InfoTheory")
        if not isinstance(unc, UncertaintyMetrics):
            raise AnomalyDetectedException("TYPE_MISMATCH: Uncertainty")
        if not isinstance(rsn, ReasoningMetrics):
            raise AnomalyDetectedException("TYPE_MISMATCH: Reasoning")
        if not isinstance(top, TopologyMetrics):
            raise AnomalyDetectedException("TYPE_MISMATCH: Topology")
        if not isinstance(ctx, ContextMetrics):
            raise AnomalyDetectedException("TYPE_MISMATCH: Context")
        if not isinstance(grd, GroundingMetrics):
            raise AnomalyDetectedException("TYPE_MISMATCH: Grounding")

        T = self.thresholds

        hallucination_risk = unc.epistemic_uncertainty * (1.0 - ctx.context_coverage_ratio)
        if hallucination_risk > T.hallucination_risk_max:
            raise AnomalyDetectedException(
                f"SUDDEN_UNCERTAINTY_SPIKE: hallucination_risk={hallucination_risk:.2f}"
            )
        if (unc.training_distribution_distance > T.off_manifold_distance_min
                and rsn.logical_validity_score < T.logical_validity_min):
            raise AnomalyDetectedException("SYSTEMIC_HALLUCINATION: off-manifold and logically invalid.")
        if (grd.grounding_confidence < T.grounding_confidence_min
                and ctx.retrieval_vs_generation_ratio < T.retrieval_ratio_min):
            raise AnomalyDetectedException("GROUNDING_FAILURE: ignoring provided factual context.")
        if (top.attention_graph_density < T.attention_density_min
                and len(top.information_flow_bottlenecks) > T.bottleneck_count_max):
            raise AnomalyDetectedException("ATTENTION_COLLAPSE: low density with many bottlenecks.")
        if (rsn.backtracking_frequency > T.backtracking_freq_max
                and rsn.contradiction_detected_count > T.contradiction_count_max):
            raise AnomalyDetectedException("REASONING_LOOP: high backtracking + contradictions.")

        return True


# =============================================================================
# §8 — Demo: telemetry
# =============================================================================

def _demo_telemetry() -> None:
    bus = TraceChannelRegistry()
    l0 = L0MetricAggregator(bus)
    bus.publish("InfoTheory", InfoTheoryMetrics(1.2, 0.5, 3.1))
    bus.publish("Uncertainty", UncertaintyMetrics(0.2, 0.1, 0.3))
    bus.publish("Reasoning", ReasoningMetrics(5, 0, 0.1, 0.95))
    bus.publish("Topology", TopologyMetrics(0.6, (), 12))
    bus.publish("Context", ContextMetrics(0.85, 0.7, 0.4))
    bus.publish("Grounding", GroundingMetrics(0.9, 0.05))
    print("[telemetry] SAFE =", l0.analyze_pre_thought_cloud())


if __name__ == "__main__":
    _demo_telemetry()
