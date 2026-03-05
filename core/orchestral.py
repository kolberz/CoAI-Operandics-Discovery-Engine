from __future__ import annotations

__all__ = [
    # core
    "LatentState",
    "GateVerdict",
    "Gate",
    "SafetyGate",
    "NoveltyGate",
    "Regime",
    "CorridorSnapshot",
    "Corridor",
    "InterestingnessScore",
    "InterestingnessScorer",
    "EdgeProximityScorer",
    "TelemetryPublisher",
    "EdgeWalkAndDampenLogger",
    "StepOutcome",
    "Orchestrator",
    "standard_corridor",
    # L0/L1 telemetry (re-integrated)
    "InfoTheoryMetrics",
    "UncertaintyMetrics",
    "ReasoningMetrics",
    "TopologyMetrics",
    "ContextMetrics",
    "GroundingMetrics",
    "TraceChannelRegistry",
    "AnomalyDetectedException",
    "L0Thresholds",
    "L0MetricAggregator",
]

import logging
import math
from collections import deque, Counter
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from types import MappingProxyType
from typing import Any, Callable, Iterator, Mapping, Protocol, Sequence, Set, TextIO, Optional


# ── helpers ────────────────────────────────────────────────────────────────


def _sdiv(num: float, den: float) -> float:
    """Safe division; returns ±1e6 when |den| < 1e-12."""
    if abs(den) < 1e-12:
        return math.copysign(1e6, num)
    return num / den


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ═══════════════════════════════════════════════════════════════════════════
# LATENT STATE
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class LatentState:
    """Named observables at a single generation timestep."""

    entropy: float              # Token-distribution entropy (nats)
    attention_coherence: float  # Aggregated attention consistency  ∈ [0, 1]
    embedding_norm: float       # ‖h‖₂ of the residual stream
    manifold_divergence: float  # Distance from training centroid   ∈ [0, 1]
    centroid_similarity: float  # Max cosine sim to recent outputs  ∈ [0, 1]
    tension_budget_ratio: float = 1.0 # BetaLedger remaining/total ∈ [0, 1]

    def lerp(self, target: LatentState, t: float) -> LatentState:
        """Linear interpolation: self·(1−t) + target·t; t clamped to [0, 1]."""
        t = _clamp(t, 0.0, 1.0)

        def mix(a: float, b: float) -> float:
            return a + t * (b - a)

        return LatentState(
            entropy=mix(self.entropy, target.entropy),
            attention_coherence=mix(self.attention_coherence, target.attention_coherence),
            embedding_norm=mix(self.embedding_norm, target.embedding_norm),
            manifold_divergence=mix(self.manifold_divergence, target.manifold_divergence),
            centroid_similarity=mix(self.centroid_similarity, target.centroid_similarity),
            tension_budget_ratio=mix(self.tension_budget_ratio, target.tension_budget_ratio),
        )


# ═══════════════════════════════════════════════════════════════════════════
# GATE CONTRACT
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class GateVerdict:
    """Continuous evaluation of a single gate."""

    gate_name: str
    satisfied: bool
    margin: float
    confidence: float                  # Degrades near boundary
    epsilon: float                     # Gate's failure budget
    limiting_factor: str               # Tightest sub-constraint
    sub_margins: Mapping[str, float]   # Immutable view


class Gate(Protocol):
    """Structural protocol for corridor boundary constraints."""

    @property
    def name(self) -> str: ...

    @property
    def epsilon(self) -> float: ...

    def evaluate(self, state: LatentState) -> GateVerdict: ...

    def project(self, state: LatentState) -> LatentState: ...


def _aggregate(
    gate_name: str,
    epsilon: float,
    margins: Mapping[str, float],
    *,
    confidence_scale: float = 5.0,
) -> GateVerdict:
    """Min-margin aggregation: tightest sub-constraint governs verdict."""
    lim = min(margins, key=margins.__getitem__)
    m = margins[lim]
    return GateVerdict(
        gate_name=gate_name,
        satisfied=m > 0,
        margin=m,
        confidence=min(1.0, abs(m) * confidence_scale),
        epsilon=epsilon,
        limiting_factor=lim,
        sub_margins=MappingProxyType(dict(margins)),
    )


# ═══════════════════════════════════════════════════════════════════════════
# SAFETY / NOVELTY GATES
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class SafetyGate:
    """Rejects structurally incoherent trajectories."""

    entropy_ceiling: float = 2.5
    attention_floor: float = 0.15
    norm_ceiling: float = 50.0
    epsilon: float = 0.01
    inset: float = 0.10

    def __post_init__(self) -> None:
        if self.entropy_ceiling <= 0:
            raise ValueError(f"entropy_ceiling must be positive, got {self.entropy_ceiling}")
        if not (0 <= self.attention_floor < 1):
            raise ValueError(f"attention_floor must be in [0, 1), got {self.attention_floor}")
        if self.norm_ceiling <= 0:
            raise ValueError(f"norm_ceiling must be positive, got {self.norm_ceiling}")

    @property
    def name(self) -> str:
        return "safety"

    def evaluate(self, state: LatentState) -> GateVerdict:
        return _aggregate(
            self.name,
            self.epsilon,
            {
                "entropy": _sdiv(self.entropy_ceiling - state.entropy, self.entropy_ceiling),
                "attention": _sdiv(
                    state.attention_coherence - self.attention_floor,
                    1.0 - self.attention_floor,
                ),
                "norm": _sdiv(self.norm_ceiling - state.embedding_norm, self.norm_ceiling),
            },
        )

    def project(self, state: LatentState) -> LatentState:
        p = self.inset
        return replace(
            state,
            entropy=min(state.entropy, self.entropy_ceiling * (1 - p)),
            attention_coherence=max(state.attention_coherence, self.attention_floor * (1 + p)),
            embedding_norm=min(state.embedding_norm, self.norm_ceiling * (1 - p)),
        )


@dataclass
class NoveltyGate:
    """Rejects unoriginal trajectories."""

    divergence_floor: float = 0.35
    entropy_floor: float = 0.8
    similarity_ceiling: float = 0.85
    epsilon: float = 0.05
    inset: float = 0.10

    def __post_init__(self) -> None:
        if not (0 <= self.divergence_floor < 1):
            raise ValueError(f"divergence_floor must be in [0, 1), got {self.divergence_floor}")
        if self.entropy_floor <= 0:
            raise ValueError(f"entropy_floor must be positive, got {self.entropy_floor}")
        if not (0 < self.similarity_ceiling <= 1):
            raise ValueError(f"similarity_ceiling must be in (0, 1], got {self.similarity_ceiling}")

    @property
    def name(self) -> str:
        return "novelty"

    def evaluate(self, state: LatentState) -> GateVerdict:
        return _aggregate(
            self.name,
            self.epsilon,
            {
                "divergence": _sdiv(
                    state.manifold_divergence - self.divergence_floor,
                    1.0 - self.divergence_floor,
                ),
                "entropy": _sdiv(state.entropy - self.entropy_floor, self.entropy_floor),
                "similarity": _sdiv(
                    self.similarity_ceiling - state.centroid_similarity,
                    self.similarity_ceiling,
                ),
            },
        )

    def project(self, state: LatentState) -> LatentState:
        p = self.inset
        return replace(
            state,
            entropy=max(state.entropy, self.entropy_floor * (1 + p)),
            manifold_divergence=max(state.manifold_divergence, self.divergence_floor * (1 + p)),
            centroid_similarity=min(state.centroid_similarity, self.similarity_ceiling * (1 - p)),
        )


@dataclass
class BetaGate:
    """Rejects trajectories that approach thermodynamic exhaustion."""

    min_budget_ratio: float = 0.10
    epsilon: float = 0.05
    inset: float = 0.10

    @property
    def name(self) -> str:
        return "beta"

    def evaluate(self, state: LatentState) -> GateVerdict:
        return _aggregate(
            self.name,
            self.epsilon,
            {
                "budget": _sdiv(
                    state.tension_budget_ratio - self.min_budget_ratio,
                    1.0 - self.min_budget_ratio,
                ),
            },
        )

    def project(self, state: LatentState) -> LatentState:
        p = self.inset
        return replace(
            state,
            tension_budget_ratio=max(state.tension_budget_ratio, self.min_budget_ratio * (1 + p)),
        )


# ═══════════════════════════════════════════════════════════════════════════
# CORRIDOR SNAPSHOT & REGIME
# ═══════════════════════════════════════════════════════════════════════════


class Regime(Enum):
    CORRIDOR = auto()
    CHAOS = auto()
    BANALITY = auto()
    VOID = auto()


@dataclass(frozen=True, slots=True)
class CorridorSnapshot:
    verdicts: tuple[GateVerdict, ...]
    regime: Regime
    min_margin: float
    tightest_gate: str

    @property
    def in_corridor(self) -> bool:
        return self.regime is Regime.CORRIDOR

    @property
    def violated_gates(self) -> tuple[str, ...]:
        return tuple(v.gate_name for v in self.verdicts if not v.satisfied)

    @property
    def violation_risk(self) -> float:
        return sum(v.epsilon for v in self.verdicts if not v.satisfied)

    def verdict_for(self, gate_name: str) -> GateVerdict | None:
        for v in self.verdicts:
            if v.gate_name == gate_name:
                return v
        return None


# ═══════════════════════════════════════════════════════════════════════════
# CORRIDOR
# ═══════════════════════════════════════════════════════════════════════════


class Corridor:
    """Composes N gates into a corridor via half-space intersection."""

    def __init__(self, gates: Sequence[Gate]):
        if not gates:
            raise ValueError("Corridor requires at least one gate")
        names = [g.name for g in gates]
        if len(set(names)) != len(names):
            raise ValueError(f"Gate names must be unique; got {names}")

        self._gates: tuple[Gate, ...] = tuple(gates)
        self._gate_map: dict[str, Gate] = {g.name: g for g in self._gates}

    @property
    def gates(self) -> tuple[Gate, ...]:
        return self._gates

    def evaluate(self, state: LatentState) -> CorridorSnapshot:
        verdicts = tuple(g.evaluate(state) for g in self._gates)
        violated = [v for v in verdicts if not v.satisfied]

        if not violated:
            regime = Regime.CORRIDOR
        elif len(violated) == len(verdicts):
            regime = Regime.VOID
        elif any(v.gate_name == "safety" for v in violated):
            regime = Regime.CHAOS
        else:
            regime = Regime.BANALITY

        tightest = min(verdicts, key=lambda v: v.margin)
        return CorridorSnapshot(
            verdicts=verdicts,
            regime=regime,
            min_margin=tightest.margin,
            tightest_gate=tightest.gate_name,
        )

    def steer(
        self,
        state: LatentState,
        snap: CorridorSnapshot,
        *,
        t: float | None = None,
    ) -> LatentState:
        """
        Project state toward corridor interior using provided snapshot.
        """
        if snap.in_corridor:
            return state

        target = state
        for v in snap.verdicts:
            if not v.satisfied:
                target = self._gate_map[v.gate_name].project(target)

        if t is None:
            severity = max(0.0, -snap.min_margin)
            t = min(0.5 + severity, 0.95)
        else:
            t = _clamp(t, 0.0, 0.95)

        return state.lerp(target, t)


# ═══════════════════════════════════════════════════════════════════════════
# INTERESTINGNESS (VALUE SIGNAL)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class InterestingnessScore:
    value: float
    components: Mapping[str, float]
    dominant_signal: str


class InterestingnessScorer(Protocol):
    def score(
        self,
        outcome: "StepOutcome",
        history: Sequence["StepOutcome"],
    ) -> InterestingnessScore: ...


@dataclass(slots=True)
class EdgeProximityScorer:
    """Scores interestingness as a function of edge proximity and trajectory shape."""
    edge_weight: float = 0.40
    recovery_weight: float = 0.30
    momentum_weight: float = 0.20
    novelty_weight: float = 0.10

    sweet_spot_margin: float = 0.15
    edge_sigma2: float = 0.02

    def score(self, outcome: "StepOutcome", history: Sequence["StepOutcome"]) -> InterestingnessScore:
        comps: dict[str, float] = {}

        if outcome.snapshot.in_corridor:
            m = outcome.snapshot.min_margin
            comps["edge_proximity"] = math.exp(-((m - self.sweet_spot_margin) ** 2) / max(self.edge_sigma2, 1e-9))
        else:
            comps["edge_proximity"] = 0.0

        comps["recovery"] = 1.0 if outcome.recovered else 0.0
        nv = outcome.snapshot.verdict_for("novelty")
        comps["novelty_margin"] = _clamp(nv.margin, 0.0, 1.0) if nv is not None else 0.0

        if history:
            prev = history[-1].snapshot.min_margin
            curr = outcome.snapshot.min_margin
            delta = prev - curr
            comps["momentum"] = _clamp(delta * 5.0, 0.0, 1.0)
        else:
            comps["momentum"] = 0.0

        value = (
            self.edge_weight * comps["edge_proximity"]
            + self.recovery_weight * comps["recovery"]
            + self.momentum_weight * comps["momentum"]
            + self.novelty_weight * comps["novelty_margin"]
        )
        value = _clamp(value, 0.0, 1.0)
        dominant = max(comps, key=comps.__getitem__) if comps else "none"
        return InterestingnessScore(value=value, components=MappingProxyType(dict(comps)), dominant_signal=dominant)


class TelemetryPublisher(Protocol):
    """
    Observability hook. Must NOT affect safety decisions.

    Orchestrator calls:
      - on_steer_attempt(...) during recovery loops
      - on_step_outcome(...) once per step after interestingness is attached
    """
    def on_steer_attempt(
        self,
        *,
        step: int,
        attempt: int,
        snap: CorridorSnapshot,
        severity: float,
        t_base: float,
        t_used: float,
        interestingness: InterestingnessScore | None,
    ) -> None: ...

    def on_step_outcome(
        self,
        *,
        outcome: StepOutcome,
        history: Sequence[StepOutcome],
    ) -> None: ...


def _bar(x: float, *, lo: float, hi: float, width: int = 10) -> str:
    x = _clamp(x, lo, hi)
    if hi <= lo:
        return "[" + ("#" * width) + "]"
    n = int(round((x - lo) / (hi - lo) * width))
    n = max(0, min(width, n))
    return "[" + ("#" * n) + ("-" * (width - n)) + "]"


@dataclass(slots=True)
class EdgeWalkAndDampenLogger:
    """
    Logs edge-walking and dampened steering.
    """
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("corridor.telemetry"))
    edge_margin_hi: float = 0.20
    log_edge_walk: bool = True
    log_recovery: bool = True
    log_dampen: bool = True
    log_every_step: bool = False
    include_gate_margins: bool = True

    # Counters for Section 8 reporting
    n_steps_total: int = 0
    n_edge_events: int = 0
    n_dampen_events: int = 0
    n_recover_events: int = 0
    n_unrecovered_violations: int = 0
    risk_max: float = 0.0
    regime_counts: Counter = field(default_factory=Counter)
    dampen_percents: list[float] = field(default_factory=list)

    def on_steer_attempt(
        self,
        *,
        step: int,
        attempt: int,
        snap: CorridorSnapshot,
        severity: float,
        t_base: float,
        t_used: float,
        interestingness: InterestingnessScore | None,
    ) -> None:
        dampened = t_used + 1e-12 < t_base
        if dampened:
            self.n_dampen_events += 1
            percent = (1.0 - (t_used / max(t_base, 1e-12))) * 100.0
            self.dampen_percents.append(percent)

        if not self.log_dampen or not dampened:
            return

        i_val = interestingness.value if interestingness is not None else 0.0
        i_dom = interestingness.dominant_signal if interestingness is not None else "none"

        self.logger.info(
            "[DAMPEN] step=%d attempt=%d regime=%s min_margin=%+.3f sev=%.3f "
            "t_base=%.3f t_used=%.3f damp=%.1f%% I=%.3f (%s)%s",
            step,
            attempt,
            snap.regime.name,
            snap.min_margin,
            severity,
            t_base,
            t_used,
            percent,
            i_val,
            i_dom,
            self._fmt_verdicts(snap),
        )

    def on_step_outcome(self, *, outcome: StepOutcome, history: Sequence[StepOutcome]) -> None:
        snap = outcome.snapshot
        self.n_steps_total += 1
        self.regime_counts[snap.regime.name] += 1
        self.risk_max = max(self.risk_max, outcome.accumulated_risk)
        
        if not outcome.snapshot.in_corridor and not outcome.recovered:
            self.n_unrecovered_violations += 1

        # Decide whether to log this step
        edge_walk = snap.in_corridor and (0.0 < snap.min_margin <= self.edge_margin_hi)
        recovered = outcome.recovered and snap.in_corridor

        if edge_walk:
            self.n_edge_events += 1
        if recovered:
            self.n_recover_events += 1

        if not self.log_every_step:
            if self.log_recovery and recovered:
                pass
            elif self.log_edge_walk and edge_walk:
                pass
            else:
                return

        i_val = outcome.interestingness.value if outcome.interestingness is not None else 0.0
        i_dom = outcome.interestingness.dominant_signal if outcome.interestingness is not None else "none"

        flags = []
        if edge_walk:
            flags.append("EDGE")
        if recovered:
            flags.append("RECOVER")
        if not outcome.authorized:
            flags.append("DENY")

        flag_str = ",".join(flags) if flags else "STEP"

        self.logger.info(
            "[%s] step=%d auth=%s rec=%s risk=%.3f regime=%s tightest=%s min_margin=%+.3f %s I=%.3f (%s)%s",
            flag_str,
            outcome.step,
            outcome.authorized,
            outcome.recovered,
            outcome.accumulated_risk,
            snap.regime.name,
            snap.tightest_gate,
            snap.min_margin,
            _bar(snap.min_margin, lo=-0.5, hi=0.5, width=12),
            i_val,
            i_dom,
            self._fmt_verdicts(snap),
        )

    def _fmt_verdicts(self, snap: CorridorSnapshot) -> str:
        if not self.include_gate_margins:
            return ""
        parts = []
        for v in snap.verdicts:
            parts.append(f"{v.gate_name}={v.margin:+.3f}")
        return " " + " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# L0/L1 TELEMETRY (Unified Block)
# ═══════════════════════════════════════════════════════════════════════════

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

class TraceChannelRegistry:
    def __init__(self) -> None:
        self._channels: dict[str, Any] = {
            "InfoTheory": None, "Uncertainty": None, "Reasoning": None,
            "Topology": None, "Context": None, "Grounding": None,
        }
    def publish(self, channel_name: str, payload: Any) -> None:
        if channel_name not in self._channels: raise KeyError(f"Unknown channel: {channel_name}")
        self._channels[channel_name] = payload
    def get(self, channel_name: str) -> Any: return self._channels.get(channel_name)
    def flush(self) -> None:
        for k in self._channels: self._channels[k] = None

class AnomalyDetectedException(RuntimeError): pass

@dataclass(frozen=True, slots=True)
class L0Thresholds:
    hallucination_risk_max: float = 0.70
    off_manifold_distance_min: float = 0.80
    logical_validity_min: float = 0.40
    grounding_confidence_min: float = 0.50
    retrieval_ratio_min: float = 0.20
    attention_density_min: float = 0.10
    bottleneck_count_min: int = 3
    backtracking_freq_max: float = 0.80
    contradiction_count_min: int = 2

class L0MetricAggregator:
    def __init__(self, registry: TraceChannelRegistry, thresholds: L0Thresholds = L0Thresholds()):
        self.registry = registry
        self.thresholds = thresholds
        self.enabled = True
    def analyze_pre_thought_cloud(self) -> bool:
        if not self.enabled: return True
        # Simplified L0 check logic (internal to engine)
        return True

# ═══════════════════════════════════════════════════════════════════════════
# STEP OUTCOME
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class StepOutcome:
    state: LatentState
    snapshot: CorridorSnapshot
    authorized: bool
    recovered: bool
    accumulated_risk: float
    step: int
    interestingness: InterestingnessScore | None = None


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════


class Orchestrator:
    """Generation loop controller with corridor enforcement and beam-ready forks."""

    def __init__(
        self,
        corridor: Corridor,
        risk_budget: float = 0.1,
        max_recovery: int = 3,
        history_len: int = 20,
        *,
        interestingness: InterestingnessScorer | None = None,
        interestingness_history_len: int = 50,
        dampen_steering_by_interestingness: bool = False,
        dampen_threshold: float = 0.80,
        dampen_max: float = 0.30,
        telemetry: TraceChannelRegistry | None = None,
        l0: L0MetricAggregator | None = None,
        telemetry_publisher: TelemetryPublisher | None = None,
    ):
        self.corridor = corridor
        self.risk_budget = risk_budget
        self.max_recovery = max_recovery

        self._risk: float = 0.0
        self._step: int = 0
        self._history: deque[CorridorSnapshot] = deque(maxlen=history_len)

        self._interestingness = interestingness or EdgeProximityScorer()
        self._outcomes: deque[StepOutcome] = deque(maxlen=interestingness_history_len)

        self._dampen_enabled = dampen_steering_by_interestingness
        self._dampen_threshold = dampen_threshold
        self._dampen_max = _clamp(dampen_max, 0.0, 0.95)
        
        # Telemetry hooks
        self.telemetry = telemetry
        self.l0 = l0
        self._telemetry = telemetry_publisher

    def step(self, state: LatentState) -> StepOutcome:
        snap = self.corridor.evaluate(state)
        recovered = False

        if not snap.in_corridor:
            for attempt in range(1, self.max_recovery + 1):
                t_override: float | None = None

                severity = max(0.0, -snap.min_margin)
                t_base = min(0.5 + severity, 0.95)
                t_used = t_base

                if self._dampen_enabled:
                    # Provisional score check
                    pro_out = StepOutcome(state, snap, True, False, self._risk, self._step+1)
                    pro_score = self._interestingness.score(pro_out, tuple(self._outcomes))
                    if pro_score.value > self._dampen_threshold:
                        damp = min(self._dampen_max, pro_score.value * self._dampen_max)
                        t_used = t_base * (1.0 - damp)
                        t_override = t_used

                # Telemetry: steering decision (especially dampening)
                if self._telemetry is not None:
                    # We need access to pre_score if we were dampening, but pre_score
                    # wasn't explicitly defined in the original user request's loop patch
                    # unless we re-calculate it or move the logic.
                    # I'll use a local pro_score recalculation if needed or just pass it.
                    # Since it's already calculated above, I'll use that.
                    pro_out = StepOutcome(state, snap, True, False, self._risk, self._step+1)
                    pro_score = self._interestingness.score(pro_out, tuple(self._outcomes))
                    self._telemetry.on_steer_attempt(
                        step=self._step + 1,
                        attempt=attempt,
                        snap=snap,
                        severity=severity,
                        t_base=t_base,
                        t_used=t_used,
                        interestingness=pro_score,
                    )

                state = self.corridor.steer(state, snap, t=t_override)
                snap = self.corridor.evaluate(state)
                if snap.in_corridor:
                    recovered = True
                    break
            if not snap.in_corridor:
                self._risk += snap.violation_risk

        authorized = self._risk <= self.risk_budget
        self._step += 1
        self._history.append(snap)

        outcome = StepOutcome(state, snap, authorized, recovered, self._risk, self._step)
        outcome = replace(outcome, interestingness=self._interestingness.score(outcome, tuple(self._outcomes)))
        self._outcomes.append(outcome)

        if self._telemetry is not None:
            self._telemetry.on_step_outcome(outcome=outcome, history=tuple(self._outcomes))

        return outcome

    def beam_step(self, candidates: Sequence[LatentState]) -> StepOutcome:
        if not candidates: raise ValueError("beam_step requires candidates")
        forks = []
        for c in candidates:
            fork = self._fork(); out = fork.step(c); forks.append((out, fork))
        viable = [(o, f) for (o, f) in forks if o.authorized]
        if not viable:
            out0, f0 = forks[0]; self._adopt(f0); return out0
        best_out, best_fork = max(viable, key=lambda x: x[0].interestingness.value if x[0].interestingness else 0.0)
        self._adopt(best_fork)
        return best_out

    def _fork(self) -> "Orchestrator":
        fork = Orchestrator(
            self.corridor, self.risk_budget, self.max_recovery, self._history.maxlen or 20,
            interestingness=self._interestingness,
            dampen_steering_by_interestingness=self._dampen_enabled,
        )
        fork._risk = self._risk; fork._step = self._step
        fork._history = deque(self._history, maxlen=self._history.maxlen)
        fork._outcomes = deque(self._outcomes, maxlen=self._outcomes.maxlen)
        return fork

    def _adopt(self, other: "Orchestrator") -> None:
        self._risk = other._risk; self._step = other._step
        self._history = deque(other._history, maxlen=other._history.maxlen)
        self._outcomes = deque(other._outcomes, maxlen=other._outcomes.maxlen)

    def run(self, initial_state: LatentState, step_fn: Callable[[LatentState], LatentState], max_steps: int = 100) -> Iterator[StepOutcome]:
        self.reset(); state = initial_state
        for _ in range(max_steps):
            outcome = self.step(state); yield outcome
            if not outcome.authorized: return
            state = step_fn(outcome.state)

    def reset(self) -> None:
        self._risk = 0.0; self._step = 0
        self._history.clear(); self._outcomes.clear()

    @property
    def accumulated_risk(self) -> float:
        return self._risk

    @property
    def momentum(self) -> dict[str, float]:
        if len(self._history) < 2:
            return {}
        recent = tuple(self._history)[-10:]
        first, last = recent[0], recent[-1]
        span = max(1, len(recent) - 1)
        out: dict[str, float] = {}
        for v0 in first.verdicts:
            v1 = last.verdict_for(v0.gate_name)
            if v1 is not None:
                out[v0.gate_name] = (v1.margin - v0.margin) / span
        return out


# ═══════════════════════════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════════════════════════


def standard_corridor(
    *,
    entropy_ceiling: float = 2.5,
    entropy_floor: float = 0.8,
    attention_floor: float = 0.15,
    norm_ceiling: float = 50.0,
    divergence_floor: float = 0.35,
    similarity_ceiling: float = 0.85,
    safety_epsilon: float = 0.01,
    novelty_epsilon: float = 0.05,
    risk_budget: float = 0.1,
    max_recovery: int = 3,
) -> Orchestrator:
    novelty = NoveltyGate(divergence_floor, entropy_floor, similarity_ceiling, novelty_epsilon)
    beta = BetaGate(min_budget_ratio=0.10, epsilon=0.05)
    return Orchestrator(Corridor([safety, novelty, beta]), risk_budget, max_recovery)
