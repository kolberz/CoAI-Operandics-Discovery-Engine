"""
coai/interface.py  (v3.1.1)

The formal boundary between the Lean 4 kernel and the Python runtime.
Every invariant here mirrors a Lean structure field or theorem precondition.
"""
from dataclasses import dataclass
from typing import Callable, Any, Protocol, TypeVar
from enum import Enum, auto
import math
import subprocess
import warnings

S = TypeVar('S')

# ---------------------------------------------------------
# PHYSICAL DIMENSIONS
# ---------------------------------------------------------
@dataclass(frozen=True)
class Dimension:
    time: int = 0
    energy: int = 0
    info: int = 0

DIM_DIMENSIONLESS = Dimension(0, 0, 0)

@dataclass(frozen=True)
class PhysInterval:
    lo: float
    hi: float
    dim: Dimension

    def __post_init__(self):
        if not isinstance(self.lo, (int, float)) or not isinstance(self.hi, (int, float)):
            raise TypeError("Interval bounds must be numeric.")
        if math.isnan(self.lo) or math.isnan(self.hi):
            raise ValueError("NaN detected in bounds.")
        if self.lo > self.hi:
            raise ValueError(f"Inverted interval: [{self.lo}, {self.hi}]")

    def __add__(self, other: "PhysInterval") -> "PhysInterval":
        if self.dim != other.dim:
            raise TypeError(f"Dimensionality mismatch: {self.dim} != {other.dim}")
        return PhysInterval(self.lo + other.lo, self.hi + other.hi, self.dim)

# ---------------------------------------------------------
# SMT COMPATIBILITY CHECKING
# ---------------------------------------------------------
class CompatibilityVerdict(Enum):
    PROVEN = auto()
    REFUTED = auto()
    UNKNOWN = auto()
    UNTRUSTED = auto()

class SMTCompatibilityChecker:
    """
    Verifies forall s, G1(s) -> A2(s) by checking UNSAT of exists s, G1(s) and not A2(s).
    """
    def __init__(self, timeout_ms: int = 5000):
        self.timeout_ms = timeout_ms

    def check(
        self,
        guarantee_smt: str,
        assumption_smt: str,
        preamble: str = "(declare-const s Int)",
    ) -> CompatibilityVerdict:
        query = (
            f"(set-logic ALL)\n"
            f"(set-option :timeout {self.timeout_ms})\n"
            f"{preamble}\n"
            f"(assert (and {guarantee_smt} (not {assumption_smt})))\n"
            f"(check-sat)\n"
        )
        try:
            result = subprocess.run(
                ["z3", "-in"],
                input=query,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return CompatibilityVerdict.UNKNOWN
            output = result.stdout.strip()
            if output == "unsat":
                return CompatibilityVerdict.PROVEN
            elif output == "sat":
                return CompatibilityVerdict.REFUTED
            return CompatibilityVerdict.UNKNOWN
        except FileNotFoundError:
            return CompatibilityVerdict.UNTRUSTED
        except subprocess.TimeoutExpired:
            return CompatibilityVerdict.UNKNOWN

# ---------------------------------------------------------
# CONTRACTS 
# ---------------------------------------------------------
@dataclass(frozen=True)
class Contract:
    """
    Mirrors CoAI.Composition.Contract in Lean 4.
    """
    assumption: Callable[[Any], bool]
    guarantee: Callable[[Any], bool]
    epsilon: float
    assumption_smt: str = ""
    guarantee_smt: str = ""

    def __post_init__(self):
        if not isinstance(self.epsilon, (int, float)):
            raise TypeError(f"epsilon must be numeric, got {type(self.epsilon)}")
        if math.isnan(self.epsilon):
            raise ValueError("Contract.epsilon is NaN")
        if self.epsilon < 0:
            raise ValueError(f"Contract.eps_nonneg violated: epsilon={self.epsilon}")
        # No upper bound check — matches Lean exactly.

    @property
    def is_vacuous(self) -> bool:
        """A bound ≥ 1 provides no safety guarantee."""
        return self.epsilon >= 1.0

    def check_compatibility(
        self,
        other: "Contract",
        checker: SMTCompatibilityChecker = None,
    ) -> CompatibilityVerdict:
        if checker is None:
            return CompatibilityVerdict.UNTRUSTED
        if self.guarantee_smt and other.assumption_smt:
            return checker.check(self.guarantee_smt, other.assumption_smt)
        return CompatibilityVerdict.UNTRUSTED

# ---------------------------------------------------------
# RISK PROFILE 
# ---------------------------------------------------------
@dataclass(frozen=True)
class RiskProfile:
    """
    Separates formal probability bound (epsilon) from domain consequence estimate.
    """
    epsilon: float
    consequence: float

    def __post_init__(self):
        if self.epsilon < 0:
            raise ValueError(f"epsilon must be non-negative, got {self.epsilon}")
        if self.consequence < 0:
            raise ValueError(f"consequence must be non-negative, got {self.consequence}")
        if self.epsilon > 1.0:
            warnings.warn(
                f"RiskProfile.epsilon={self.epsilon} > 1.0: bound is vacuous. "
                f"Expected risk capped at consequence={self.consequence}.",
                stacklevel=2,
            )

    @property
    def expected_risk(self) -> float:
        """E[loss] = min(epsilon, 1) × consequence."""
        return min(self.epsilon, 1.0) * self.consequence

    @property
    def is_vacuous(self) -> bool:
        return self.epsilon >= 1.0

# ---------------------------------------------------------
# COMPOSITION 
# ---------------------------------------------------------
@dataclass(frozen=True)
class CompositionResult:
    """Output of sequential composition, bounded by Lean Theorem 2.1."""
    epsilon_bound: float

    @staticmethod
    def seq_compose(c1: Contract, c2: Contract) -> "CompositionResult":
        """Union bound: epsilon1 + epsilon2. Matches the proven Lean theorem exactly."""
        return CompositionResult(epsilon_bound=c1.epsilon + c2.epsilon)

# ---------------------------------------------------------
# ECONOMICS
# ---------------------------------------------------------
@dataclass(frozen=True)
class ValueParams:
    """Mirrors CoAI.Economics.EconomicsParams."""
    lambda_R: float
    lambda_C: float
    lambda_v: float



def compute_value_objective_interval(
    utility: PhysInterval,
    risk: PhysInterval,
    tco: PhysInterval,
    params: ValueParams,
) -> PhysInterval:
    """
    Conservative interval evaluation of ValueObjective.
    """
    if (
        utility.dim != DIM_DIMENSIONLESS
        or risk.dim != DIM_DIMENSIONLESS
        or tco.dim != DIM_DIMENSIONLESS
    ):
        raise TypeError("Value computation requires dimensionless inputs.")
    worst = utility.lo - (params.lambda_R * risk.hi) - (params.lambda_C * tco.hi)
    best = utility.hi - (params.lambda_R * risk.lo) - (params.lambda_C * tco.lo)
    return PhysInterval(lo=worst, hi=best, dim=DIM_DIMENSIONLESS)
