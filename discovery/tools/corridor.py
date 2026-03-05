from __future__ import annotations

__all__ = [
    "CorridorToolConfig",
    "LatentState",
    "GateVerdict",
    "Gate",
    "SafetyGate",
    "NoveltyGate",
    "TrustGate",
    "Regime",
    "CorridorSnapshot",
    "Corridor",
    "StepOutcome",
    "Orchestrator",
    "OperandicsCorridorTool",
    "standard_corridor",
    "load_corridor_orchestrator",
]

import math
from collections import Counter, deque
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from types import MappingProxyType
from typing import Any, Callable, Iterator, Mapping, Protocol, Sequence


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AnomalyDetectedException(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sdiv(num: float, den: float) -> float:
    """Safe division; returns ±1e6 when |den| < 1e-12."""
    if abs(den) < 1e-12:
        return math.copysign(1e6, num)
    return num / den


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# LatentState
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LatentState:
    entropy: float
    attention_coherence: float
    embedding_norm: float
    manifold_divergence: float
    centroid_similarity: float
    tension_budget_ratio: float = 1.0 # BetaLedger remaining/total ∈ [0, 1]

    def lerp(self, target: LatentState, t: float) -> LatentState:
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


# ---------------------------------------------------------------------------
# Gate contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GateVerdict:
    gate_name: str
    satisfied: bool
    margin: float
    confidence: float
    epsilon: float
    limiting_factor: str
    sub_margins: Mapping[str, float]


class Gate(Protocol):
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


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

@dataclass
class SafetyGate:
    entropy_ceiling: float = 2.5
    attention_floor: float = 0.15
    norm_ceiling: float = 50.0
    epsilon: float = 0.01
    inset: float = 0.10

    @property
    def name(self) -> str:
        return "safety"

    def evaluate(self, state: LatentState) -> GateVerdict:
        return _aggregate(
            self.name,
            self.epsilon,
            {
                "entropy": _sdiv(self.entropy_ceiling - state.entropy, self.entropy_ceiling),
                "attention": _sdiv(state.attention_coherence - self.attention_floor, 1.0 - self.attention_floor),
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
    divergence_floor: float = 0.35
    entropy_floor: float = 0.8
    similarity_ceiling: float = 0.85
    epsilon: float = 0.05
    inset: float = 0.10

    @property
    def name(self) -> str:
        return "novelty"

    def evaluate(self, state: LatentState) -> GateVerdict:
        return _aggregate(
            self.name,
            self.epsilon,
            {
                "divergence": _sdiv(state.manifold_divergence - self.divergence_floor, 1.0 - self.divergence_floor),
                "entropy": _sdiv(state.entropy - self.entropy_floor, self.entropy_floor),
                "similarity": _sdiv(self.similarity_ceiling - state.centroid_similarity, self.similarity_ceiling),
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
                    1.0 - self.min_budget_ratio
                ),
            },
        )

    def project(self, state: LatentState) -> LatentState:
        p = self.inset
        return replace(
            state,
            tension_budget_ratio=max(state.tension_budget_ratio, self.min_budget_ratio * (1 + p)),
        )


@dataclass
class TrustGate:
    required_loaded: bool = True
    epsilon: float = 0.001
    name_override: str = "trust"

    @property
    def name(self) -> str:
        return self.name_override

    def evaluate(self, state: LatentState) -> GateVerdict:
        return _aggregate(self.name, self.epsilon, {"trust": 1.0})

    def project(self, state: LatentState) -> LatentState:
        return state


# ---------------------------------------------------------------------------
# Corridor snapshot and regime
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Corridor: composition of N gates
# ---------------------------------------------------------------------------

class Corridor:
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

    def steer(self, state: LatentState, snap: CorridorSnapshot) -> LatentState:
        if snap.in_corridor:
            return state

        target = state
        for v in snap.verdicts:
            if not v.satisfied:
                target = self._gate_map[v.gate_name].project(target)

        severity = max(0.0, -snap.min_margin)
        t = min(0.5 + severity, 0.95)
        return state.lerp(target, t)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class StepOutcome:
    state: LatentState
    snapshot: CorridorSnapshot
    authorized: bool
    recovered: bool
    accumulated_risk: float
    step: int


class Orchestrator:
    def __init__(self, corridor: Corridor, risk_budget: float = 0.1, max_recovery: int = 3, history_len: int = 20):
        self.corridor = corridor
        self.risk_budget = risk_budget
        self.max_recovery = max_recovery
        self._risk: float = 0.0
        self._step: int = 0
        self._history: deque[CorridorSnapshot] = deque(maxlen=history_len)

    def observe(self, state: LatentState) -> StepOutcome:
        snap = self.corridor.evaluate(state)
        recovered = False

        if not snap.in_corridor:
            for _ in range(self.max_recovery):
                state = self.corridor.steer(state, snap)
                snap = self.corridor.evaluate(state)
                if snap.in_corridor:
                    recovered = True
                    break

            if not snap.in_corridor:
                self._risk += snap.violation_risk

        authorized = self._risk <= self.risk_budget
        self._step += 1
        self._history.append(snap)

        return StepOutcome(
            state=state,
            snapshot=snap,
            authorized=authorized,
            recovered=recovered,
            accumulated_risk=self._risk,
            step=self._step,
        )

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

    def reset(self) -> None:
        self._risk = 0.0
        self._step = 0
        self._history.clear()


# ---------------------------------------------------------------------------
# Tool integration layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CorridorToolConfig:
    certified_mode: bool = False
    fail_on_unauthorized: bool = True
    min_attention_coherence: float | None = None


class OperandicsCorridorTool:
    def __init__(
        self,
        orchestrator: Orchestrator,
        *,
        config: CorridorToolConfig,
        state_fn: Callable[[Any], LatentState],
    ):
        self.orchestrator = orchestrator
        self.config = config
        self.state_fn = state_fn
        self._expected_bundle_sha: str | None = None

    def on_session_start(self, session: Any) -> None:
        md = getattr(session, "metadata", {}) or {}

        if self.config.certified_mode:
            if not md.get("attention_bundle_loaded", False):
                raise AnomalyDetectedException("CERTIFIED_MODE: verified attention bundle not loaded")

            sha = md.get("attention_bundle_sha256_16")
            if not isinstance(sha, str) or not sha:
                raise AnomalyDetectedException("CERTIFIED_MODE: missing attention bundle sha256_16 in session.metadata")

            self._expected_bundle_sha = sha

        self.orchestrator.reset()

    def on_cycle_end(self, session: Any, cycle_idx: int) -> StepOutcome:
        if self.config.certified_mode:
            md = getattr(session, "metadata", {}) or {}
            sha = md.get("attention_bundle_sha256_16")
            if self._expected_bundle_sha and sha != self._expected_bundle_sha:
                raise AnomalyDetectedException(
                    f"CERTIFIED_MODE: bundle hash changed mid-session: {sha} != {self._expected_bundle_sha}"
                )

        state = self.state_fn(session)
        if self.config.min_attention_coherence is not None:
            if state.attention_coherence < self.config.min_attention_coherence:
                raise AnomalyDetectedException(
                    f"LEAN_BOUND_VIOLATION: attention_coherence={state.attention_coherence:.4f} "
                    f"< min={self.config.min_attention_coherence:.4f}"
                )

        outcome = self.orchestrator.observe(state)
        # We don't want to crash on unauthorized for theorem discovery usually, we just log and steer.
        # But if fail_on_unauthorized is True, we crash. Let's make it a logging event mostly for Theorem Discovery.
        if self.config.fail_on_unauthorized and not outcome.authorized:
            raise AnomalyDetectedException(
                f"CORRIDOR_DEAUTH: risk_budget exceeded at cycle={cycle_idx}, "
                f"risk={outcome.accumulated_risk:.4f}, regime={outcome.snapshot.regime.name}, "
                f"violated={outcome.snapshot.violated_gates}"
            )
        return outcome


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
    safety = SafetyGate(
        entropy_ceiling=entropy_ceiling,
        attention_floor=attention_floor,
        norm_ceiling=norm_ceiling,
        epsilon=safety_epsilon,
    )
    novelty = NoveltyGate(
        divergence_floor=divergence_floor,
        entropy_floor=entropy_floor,
        similarity_ceiling=similarity_ceiling,
        epsilon=novelty_epsilon,
    )
    beta = BetaGate(min_budget_ratio=0.10, epsilon=0.05)
    return Orchestrator(
        corridor=Corridor([safety, novelty, beta]),
        risk_budget=risk_budget,
        max_recovery=max_recovery,
    )


def load_corridor_orchestrator(profile_name: str) -> Orchestrator:
    """Loads a corridor orchestrator with parameters from docs/corridor_profiles.json."""
    import json
    from pathlib import Path
    
    profile_path = Path("docs/corridor_profiles.json")
    if not profile_path.exists():
        # Fallback to standard if file missing
        print(f"Warning: {profile_path} not found, using standard defaults.")
        return standard_corridor()
        
    profiles = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile_name not in profiles:
        raise ValueError(f"Profile '{profile_name}' not found in {profile_path}")
        
    p = profiles[profile_name]
    return standard_corridor(
        entropy_ceiling=p.get("entropy_ceiling", 2.5),
        entropy_floor=p.get("entropy_floor", 0.8),
        attention_floor=p.get("attention_floor", 0.15),
        norm_ceiling=p.get("norm_ceiling", 50.0),
        divergence_floor=p.get("divergence_floor", 0.35),
        similarity_ceiling=p.get("similarity_ceiling", 0.85),
    )
