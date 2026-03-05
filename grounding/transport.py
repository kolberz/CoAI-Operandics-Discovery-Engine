"""
grounding/transport.py

System migration and optimal transport.
Implements SENTINEL Gate 6: Transport Method.

Models the COST of migrating from one system architecture
to another, enabling reasoning about architectural evolution.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from grounding.intervals import ModuleMeasurement, Interval
from grounding.dimensions import DIMENSIONLESS, ENERGY, BITS
import math


@dataclass
class SystemProfile:
    """
    Vector representation of a system's measured properties.
    Used for computing distances between architectures.
    """
    name: str
    modules: List[ModuleMeasurement]
    topology: str  # "sequential", "parallel", "mixed"
    
    def total_risk(self) -> Interval:
        if not self.modules:
            return Interval.exact(0.0)
        result = self.modules[0].risk
        for m in self.modules[1:]:
            result = result + m.risk
        return result
    
    def total_cost(self) -> Interval:
        if not self.modules:
            return Interval.exact(0.0, ENERGY)
        result = self.modules[0].cost
        for m in self.modules[1:]:
            result = result + m.cost
        return result
    
    def total_complexity(self) -> Interval:
        if not self.modules:
            return Interval.exact(0.0, BITS)
        result = self.modules[0].complexity
        for m in self.modules[1:]:
            result = result + m.complexity
        return result
    
    def min_security(self) -> Interval:
        if not self.modules:
            return Interval.exact(float('inf'), BITS)
        result = self.modules[0].security
        for m in self.modules[1:]:
            if m.security.lo < result.lo:
                result = m.security
        return result
    
    def as_vector(self) -> List[float]:
        """Flatten to numeric vector for distance computation."""
        return [
            self.total_risk().midpoint(),
            self.total_cost().midpoint(),
            self.min_security().midpoint(),
            self.total_complexity().midpoint(),
        ]


@dataclass
class MigrationStep:
    """A single step in a migration path."""
    description: str
    from_state: str
    to_state: str
    risk_during: float     # Risk during migration
    cost_of_step: float    # Energy/time cost of this step
    duration: float        # Time for this step


@dataclass
class MigrationPlan:
    """Complete plan for migrating between system architectures."""
    source: SystemProfile
    target: SystemProfile
    steps: List[MigrationStep]
    total_cost: float
    max_risk_during: float
    total_duration: float


class TransportModel:
    """
    Computes migration costs between system architectures.
    
    Uses weighted L2 distance in the (Risk, Cost, Security, Complexity)
    space as a proxy for Wasserstein-2 distance.
    
    The weights reflect the relative importance (and cost) of
    changing each dimension:
      - Changing Risk requires adding/removing redundancy
      - Changing Cost requires optimization/parallelization  
      - Changing Security requires adding/removing controls
      - Changing Complexity requires refactoring
    """
    
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or {
            "risk": 10.0,        # Hardest to change safely
            "cost": 1.0,         # Relatively easy (add resources)
            "security": 5.0,     # Moderate difficulty
            "complexity": 3.0,   # Requires careful refactoring
        }
    
    def distance(self, a: SystemProfile, b: SystemProfile) -> float:
        """
        Weighted L2 distance between two system profiles.
        Approximates the Wasserstein-2 transport cost.
        """
        va = a.as_vector()
        vb = b.as_vector()
        w = [self.weights["risk"], self.weights["cost"],
             self.weights["security"], self.weights["complexity"]]
        
        return math.sqrt(sum(
            wi * (ai - bi) ** 2 for wi, ai, bi in zip(w, va, vb)
        ))
    
    def plan_migration(self, source: SystemProfile, 
                       target: SystemProfile,
                       max_steps: int = 5) -> MigrationPlan:
        """
        Generate a migration plan that minimizes risk at each step.
        Uses greedy interpolation in the property space.
        """
        dist = self.distance(source, target)
        n_steps = min(max_steps, max(1, int(math.ceil(dist / 2.0))))
        
        steps = []
        sv = source.as_vector()
        tv = target.as_vector()
        
        for i in range(n_steps):
            frac = (i + 1) / n_steps
            prev_frac = i / n_steps
            
            # Interpolated state
            mid = [s + frac * (t - s) for s, t in zip(sv, tv)]
            prev = [s + prev_frac * (t - s) for s, t in zip(sv, tv)]
            
            step_cost = math.sqrt(sum(
                (a - b) ** 2 for a, b in zip(prev, mid)
            ))
            
            # Risk during migration is max of current and next state risk
            risk_during = max(prev[0], mid[0]) * 1.5  # 50% overhead during migration
            
            steps.append(MigrationStep(
                description=f"Step {i+1}/{n_steps}: {prev_frac:.0%} -> {frac:.0%} complete",
                from_state=f"state_{i}",
                to_state=f"state_{i+1}",
                risk_during=risk_during,
                cost_of_step=step_cost,
                duration=step_cost * 10,  # Rough: 10 time units per cost unit
            ))
        
        return MigrationPlan(
            source=source,
            target=target,
            steps=steps,
            total_cost=sum(s.cost_of_step for s in steps),
            max_risk_during=max(s.risk_during for s in steps) if steps else 0,
            total_duration=sum(s.duration for s in steps),
        )
    
    def report(self, plan: MigrationPlan) -> str:
        lines = [
            "Migration Plan",
            "=" * 50,
            f"  From: {plan.source.name}",
            f"  To:   {plan.target.name}",
            f"  Distance: {self.distance(plan.source, plan.target):.3f}",
            f"  Steps: {len(plan.steps)}",
            f"  Total cost: {plan.total_cost:.3f}",
            f"  Max risk during migration: {plan.max_risk_during:.4f}",
            f"  Total duration: {plan.total_duration:.1f} time units",
            "",
            "  Step Details:"
        ]
        for step in plan.steps:
            lines.append(
                f"    {step.description}: "
                f"cost={step.cost_of_step:.3f}, "
                f"risk={step.risk_during:.4f}, "
                f"duration={step.duration:.1f}"
            )
        return "\n".join(lines)
