"""
grounding/causal.py

Causal reasoning layer for the CoAI calculus.
Implements SENTINEL Gate 5: Causal Scope.

Key insight from older research:
  P(y | x) != P(y | do(x))
  Observing that safe systems are cheap does not mean
  MAKING a system safe will make it cheap.

This module:
  1. Classifies variables as intervenable or observable
  2. Generates causal axioms distinguishing do() from observe()
  3. Identifies confounders in cross-domain theorems
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from core.logic import (
    Term, Variable, Constant, Function, Formula,
    Equality, LessEq, Forall, Implies, Not, And,
    MODULE, REAL
)


@dataclass
class CausalVariable:
    """A variable with causal classification."""
    name: str
    role: str          # "intervenable", "observable", "contextual"
    description: str
    can_set: bool      # Can an architect directly set this?
    
    def __repr__(self):
        return f"{self.name} [{self.role}]"


@dataclass
class CausalEdge:
    """A causal relationship: cause -> effect."""
    cause: str
    effect: str
    mechanism: str     # How does cause affect effect?
    confounders: List[str] = field(default_factory=list)


class CausalModel:
    """
    Structural Causal Model for the CoAI system.
    Defines what can be intervened on and what is merely observed.
    """
    
    def __init__(self):
        self.variables: Dict[str, CausalVariable] = {}
        self.edges: List[CausalEdge] = []
        self._init_coai_model()
    
    def _init_coai_model(self):
        """Define the causal structure of the CoAI calculus."""
        
        # ── INTERVENABLE (Design Choices) ──
        self.add_variable(CausalVariable(
            "composition_type", "intervenable",
            "Choice of Seq vs Par vs Choice", True
        ))
        self.add_variable(CausalVariable(
            "barrier_placement", "intervenable",
            "Where to place synchronization barriers", True
        ))
        self.add_variable(CausalVariable(
            "filter_placement", "intervenable",
            "Where to place security filters", True
        ))
        self.add_variable(CausalVariable(
            "redundancy_level", "intervenable",
            "Number of redundant copies", True
        ))
        self.add_variable(CausalVariable(
            "branch_probability", "contextual",
            "Probability in Choice operator", False
        ))
        
        # ── OBSERVABLE (Consequences) ──
        self.add_variable(CausalVariable(
            "risk", "observable",
            "System failure probability", False
        ))
        self.add_variable(CausalVariable(
            "cost", "observable",
            "Resource consumption (energy)", False
        ))
        self.add_variable(CausalVariable(
            "security", "observable",
            "Information assurance (entropy)", False
        ))
        self.add_variable(CausalVariable(
            "complexity", "observable",
            "Structural complexity (bits)", False
        ))
        self.add_variable(CausalVariable(
            "dependency", "contextual",
            "Dependency between modules", False
        ))
        
        # ── CAUSAL EDGES ──
        
        # Design choices cause changes in measures
        self.add_edge(CausalEdge(
            "composition_type", "risk",
            "Seq: additive risk. Par: depends on Dep.",
            confounders=["dependency"]
        ))
        self.add_edge(CausalEdge(
            "composition_type", "cost",
            "Seq: additive cost. Par: max cost.",
        ))
        self.add_edge(CausalEdge(
            "composition_type", "complexity",
            "Seq: additive. Par: max.",
        ))
        self.add_edge(CausalEdge(
            "barrier_placement", "risk",
            "Adds R_PENALTY if non-trivial.",
        ))
        self.add_edge(CausalEdge(
            "filter_placement", "security",
            "Order matters: non-commutative.",
        ))
        self.add_edge(CausalEdge(
            "redundancy_level", "risk",
            "Only reduces risk if Dep < 1.",
            confounders=["dependency"]
        ))
        
        # Cross-measure causal links (confounded!)
        self.add_edge(CausalEdge(
            "composition_type", "dependency",
            "Parallelizing may introduce shared resources.",
        ))
        self.add_edge(CausalEdge(
            "risk", "cost",
            "CONFOUNDED: both caused by composition_type.",
            confounders=["composition_type"]
        ))
    
    def add_variable(self, var: CausalVariable):
        self.variables[var.name] = var
    
    def add_edge(self, edge: CausalEdge):
        self.edges.append(edge)
    
    def intervenable_variables(self) -> List[CausalVariable]:
        return [v for v in self.variables.values() if v.role == "intervenable"]
    
    def observable_variables(self) -> List[CausalVariable]:
        return [v for v in self.variables.values() if v.role == "observable"]
    
    def confounders_for(self, cause: str, effect: str) -> List[str]:
        """Find confounders in the causal path from cause to effect."""
        for edge in self.edges:
            if edge.cause == cause and edge.effect == effect:
                return edge.confounders
        return []
    
    def is_causal_claim_valid(self, cause: str, effect: str) -> Tuple[bool, str]:
        """
        Check if a causal claim (cause -> effect) is valid,
        or if it's confounded.
        """
        cause_var = self.variables.get(cause)
        if cause_var is None:
            return False, f"Unknown variable: {cause}"
        
        if not cause_var.can_set:
            return False, f"{cause} is not intervenable (cannot do({cause}))"
        
        confounders = self.confounders_for(cause, effect)
        if confounders:
            return False, (
                f"Confounded by {confounders}. "
                f"P({effect}|{cause}) != P({effect}|do({cause}))"
            )
        
        return True, f"Valid causal claim: do({cause}) -> {effect}"
    
    def audit_theorem(self, theorem_name: str, 
                      assumed_causes: List[str],
                      claimed_effects: List[str]) -> dict:
        """
        Audit a theorem for causal validity.
        Checks if the theorem's claims are causal or merely correlational.
        """
        issues = []
        valid = True
        
        for cause in assumed_causes:
            for effect in claimed_effects:
                is_valid, msg = self.is_causal_claim_valid(cause, effect)
                if not is_valid:
                    valid = False
                    issues.append(msg)
        
        return {
            "theorem": theorem_name,
            "causal_validity": valid,
            "issues": issues,
            "recommendation": (
                "Theorem is causally valid" if valid
                else "Theorem is correlational only. Requires adjustment for causal claims."
            )
        }
    
    def generate_causal_axioms(self) -> List[Tuple[Formula, str]]:
        """Generate axioms encoding the causal structure."""
        m1 = Variable("M1", MODULE)
        m2 = Variable("M2", MODULE)
        
        axioms = []
        
        # CA1: Parallelization may change dependency
        # do(composition := Par) can change Dep
        # This means: Risk(Par(A,B)) cannot be computed without
        # knowing the POST-INTERVENTION dependency
        axioms.append((
            Forall(m1, Forall(m2,
                Not(Equality(
                    Function("Dep", (m1, m2), REAL),
                    Function("Dep_post_par", (m1, m2), REAL)
                ))
            )),
            "causal_dep_change"
        ))
        
        return axioms
    
    def report(self) -> str:
        lines = ["Causal Model Report", "=" * 40]
        
        lines.append("\nIntervenable (design choices):")
        for v in self.intervenable_variables():
            lines.append(f"  do({v.name}): {v.description}")
        
        lines.append("\nObservable (consequences):")
        for v in self.observable_variables():
            lines.append(f"  observe({v.name}): {v.description}")
        
        lines.append("\nCausal edges with confounders:")
        for e in self.edges:
            conf = f" [confounders: {e.confounders}]" if e.confounders else ""
            lines.append(f"  {e.cause} -> {e.effect}{conf}")
        
        return "\n".join(lines)
