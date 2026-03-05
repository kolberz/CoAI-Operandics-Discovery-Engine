"""
grounding/intervals.py

Interval arithmetic for uncertainty propagation.
Implements SENTINEL Gate 4: Observation Model.

Every physical measurement has uncertainty. This module
propagates that uncertainty through CoAI compositions
using the algebraic theorems proved by the engine.
"""

from dataclasses import dataclass
from typing import Optional, List
from grounding.dimensions import Dimension, DIMENSIONLESS, ENERGY, BITS
import math


@dataclass
class Interval:
    """Closed interval [lo, hi] with physical dimension."""
    lo: float
    hi: float
    dim: Dimension = DIMENSIONLESS
    
    def __post_init__(self):
        if self.lo > self.hi:
            self.lo, self.hi = self.hi, self.lo
    
    @staticmethod
    def exact(value: float, dim: Dimension = DIMENSIONLESS) -> 'Interval':
        return Interval(value, value, dim)
    
    @staticmethod
    def measured(value: float, uncertainty: float,
                 dim: Dimension = DIMENSIONLESS) -> 'Interval':
        """Create from measurement: value +/- uncertainty."""
        return Interval(value - abs(uncertainty), value + abs(uncertainty), dim)
    
    @staticmethod
    def estimated(value: float, relative_error: float = 0.1,
                  dim: Dimension = DIMENSIONLESS) -> 'Interval':
        """Create from estimate with relative error (default 10%)."""
        delta = abs(value * relative_error)
        return Interval(value - delta, value + delta, dim)
    
    def width(self) -> float:
        return self.hi - self.lo
    
    def midpoint(self) -> float:
        return (self.lo + self.hi) / 2.0
    
    def relative_uncertainty(self) -> float:
        mid = self.midpoint()
        if abs(mid) < 1e-15:
            return float('inf') if self.width() > 0 else 0.0
        return self.width() / (2.0 * abs(mid))
    
    def contains(self, value: float) -> bool:
        return self.lo <= value <= self.hi
    
    def __add__(self, other: 'Interval') -> 'Interval':
        """Interval addition: [a,b] + [c,d] = [a+c, b+d]."""
        return Interval(self.lo + other.lo, self.hi + other.hi, self.dim)
    
    def __sub__(self, other: 'Interval') -> 'Interval':
        return Interval(self.lo - other.hi, self.hi - other.lo, self.dim)
    
    def scale(self, factor: float) -> 'Interval':
        if factor >= 0:
            return Interval(self.lo * factor, self.hi * factor, self.dim)
        return Interval(self.hi * factor, self.lo * factor, self.dim)
    
    def __mul__(self, other: 'Interval') -> 'Interval':
        products = [self.lo * other.lo, self.lo * other.hi,
                    self.hi * other.lo, self.hi * other.hi]
        return Interval(min(products), max(products), self.dim * other.dim)
    
    def __repr__(self):
        if abs(self.lo - self.hi) < 1e-15:
            return f"{self.lo:.4g} {self.dim}"
        return f"[{self.lo:.4g}, {self.hi:.4g}] {self.dim}"


def iv_max(a: Interval, b: Interval) -> Interval:
    """Interval max: [max(a_lo,b_lo), max(a_hi,b_hi)]."""
    return Interval(max(a.lo, b.lo), max(a.hi, b.hi), a.dim)

def iv_min(a: Interval, b: Interval) -> Interval:
    """Interval min: [min(a_lo,b_lo), min(a_hi,b_hi)]."""
    return Interval(min(a.lo, b.lo), min(a.hi, b.hi), a.dim)


# ═══════════════════════════════════════════
# MODULE MEASUREMENT
# ═══════════════════════════════════════════

@dataclass
class ModuleMeasurement:
    """
    Complete physical measurement of a module.
    Every value is an interval reflecting measurement uncertainty.
    """
    name: str
    risk: Interval         # probability [0,1], dimensionless
    cost: Interval         # energy (joules)
    security: Interval     # entropy (bits)
    complexity: Interval   # information content (bits)
    
    def summary(self) -> str:
        lines = [f"Module: {self.name}"]
        lines.append(f"  Risk:       {self.risk}  (+-{self.risk.relative_uncertainty():.0%})")
        lines.append(f"  Cost:       {self.cost}  (+-{self.cost.relative_uncertainty():.0%})")
        lines.append(f"  Security:   {self.security}  (+-{self.security.relative_uncertainty():.0%})")
        lines.append(f"  Complexity: {self.complexity}  (+-{self.complexity.relative_uncertainty():.0%})")
        return "\n".join(lines)


    def validate(self) -> List[str]:
        """
        Check physical validity.
        Returns list of error messages (empty if valid).
        """
        errors = []
        # Risk: [0, 1], dimensionless
        if self.risk.lo < 0.0 or self.risk.hi > 1.0:
            errors.append(f"Risk {self.risk} out of bounds [0,1]")
        
        # Non-negative quantities
        if self.cost.lo < 0:
            errors.append(f"Cost {self.cost} negative")
        if self.security.lo < 0:
            errors.append(f"Security {self.security} negative")
        if self.complexity.lo < 0:
            errors.append(f"Complexity {self.complexity} negative")
            
        return errors


# ═══════════════════════════════════════════
# INTERVAL PROPAGATOR
# ═══════════════════════════════════════════

class IntervalPropagator:
    """
    Propagates interval-valued measurements through compositions.
    Each method implements a PROVEN algebraic theorem with intervals.
    """
    
    def seq(self, a: ModuleMeasurement, b: ModuleMeasurement) -> ModuleMeasurement:
        """
        Sequential composition.
        Uses proven theorems:
          Risk(Seq(A,B)) = Risk(A) + Risk(B)       [additive]
          Cost(Seq(A,B)) = Cost(A) + Cost(B)        [additive]
          Ent(Seq(A,B))  = min(Ent(A), Ent(B))      [bottleneck]
          Comp(Seq(A,B)) = Comp(A) + Comp(B)         [additive, log-domain]
        """
        return ModuleMeasurement(
            name=f"Seq({a.name}, {b.name})",
            risk=a.risk + b.risk,
            cost=a.cost + b.cost,
            security=iv_min(a.security, b.security),
            complexity=a.complexity + b.complexity,
        )
    
    def par(self, a: ModuleMeasurement, b: ModuleMeasurement,
            dep: float = 0.0) -> ModuleMeasurement:
        """
        Parallel composition with dependency factor.
        Uses proven theorems:
          Cost(Par(A,B)) = max(Cost(A), Cost(B))     [bottleneck]
          Comp(Par(A,B)) = max(Comp(A), Comp(B))     [max]
          Risk: depends on Dep
            Dep=1: Risk(Par(A,A)) = Risk(A)           [idempotent]
            Dep=0: Risk(Par(A,B)) = Risk(A)*Risk(B)   [independent]
        """
        # Risk interpolation based on dependency
        if dep >= 1.0:
            par_risk = iv_max(a.risk, b.risk)
        elif dep <= 0.0:
            par_risk = a.risk * b.risk
        else:
            r_dep = iv_max(a.risk, b.risk)
            r_indep = a.risk * b.risk
            par_risk = Interval(
                dep * r_dep.lo + (1 - dep) * r_indep.lo,
                dep * r_dep.hi + (1 - dep) * r_indep.hi,
                DIMENSIONLESS
            )
        
        return ModuleMeasurement(
            name=f"Par({a.name}, {b.name})",
            risk=par_risk,
            cost=iv_max(a.cost, b.cost),
            security=iv_min(a.security, b.security),
            complexity=iv_max(a.complexity, b.complexity),
        )
    
    def choice(self, a: ModuleMeasurement, b: ModuleMeasurement,
               p: float) -> ModuleMeasurement:
        """
        Probabilistic choice.
        Risk(Choice(A,B,p)) = p*Risk(A) + (1-p)*Risk(B)
        """
        return ModuleMeasurement(
            name=f"Choice({a.name}, {b.name}, {p:.2f})",
            risk=a.risk.scale(p) + b.risk.scale(1.0 - p),
            cost=Interval(
                min(a.cost.lo, b.cost.lo),
                max(a.cost.hi, b.cost.hi),
                a.cost.dim
            ),
            security=iv_min(a.security, b.security),
            complexity=iv_max(a.complexity, b.complexity),
        )
    
    def barrier(self, m: ModuleMeasurement, trivial: bool = False,
                penalty: float = 0.03) -> ModuleMeasurement:
        """
        Barrier/synchronization.
        Risk(Barrier(M,P)) = Risk(M) + R_PENALTY  [if P non-trivial]
        Risk(Barrier(M,TRUE)) = Risk(M)            [if P trivial]
        """
        if trivial:
            return ModuleMeasurement(
                name=f"Barrier({m.name}, TRUE)",
                risk=m.risk,
                cost=m.cost,
                security=m.security,
                complexity=m.complexity,
            )
        
        penalty_iv = Interval.estimated(penalty, 0.2, DIMENSIONLESS)
        return ModuleMeasurement(
            name=f"Barrier({m.name})",
            risk=m.risk + penalty_iv,
            cost=m.cost,
            security=m.security,
            complexity=m.complexity + Interval.exact(1.0, BITS),
        )
    
    def validate_quad_goal(self, m: ModuleMeasurement,
                           landauer_factor: float) -> dict:
        """
        Validate the Quad-Goal Constraint for a specific module.
        Grounded version: Risk~0 -> Cost <= Comp * LANDAUER * overhead
        
        Returns dict with validation results.
        """
        # Convert complexity from bits to energy
        comp_energy = Interval(
            m.complexity.lo * landauer_factor,
            m.complexity.hi * landauer_factor,
            ENERGY
        )
        
        # Check if risk is near zero
        risk_near_zero = m.risk.hi < 0.01
        
        # Check if cost <= complexity (in energy units)
        cost_within_bound = m.cost.hi <= comp_energy.hi
        
        return {
            "module": m.name,
            "risk_near_zero": risk_near_zero,
            "risk": m.risk,
            "cost_energy": m.cost,
            "complexity_energy": comp_energy,
            "quad_goal_holds": not risk_near_zero or cost_within_bound,
            "message": (
                "PASS: Quad-Goal satisfied" if (not risk_near_zero or cost_within_bound)
                else f"FAIL: Cost {m.cost} exceeds Complexity-energy {comp_energy}"
            )
        }
