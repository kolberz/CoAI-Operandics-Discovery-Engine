"""
prover/heuristics.py

Semantic heuristic for guiding saturation search.
Component 3 (partial) in the nine-component architecture.
"""

from core.logic import *
from typing import Set
from grounding.quake import phantom_hash

# Domain symbols for cross-domain detection
RISK_SYMBOLS = {"Risk", "RiskDist", "E_Risk", "R_PENALTY", "R_INF", "R_ZERO"}
COST_SYMBOLS = {"ResourceCost", "Cost", "Latency"}
SECURITY_SYMBOLS = {"Ent", "Entropy", "Sec_Filter", "Security"}
COMPLEXITY_SYMBOLS = {"Comp", "Complexity"}
COMPOSITION_SYMBOLS = {"Seq", "Par_Dyn", "Par", "Choice", "Barrier"}

ALL_DOMAIN_SETS = [RISK_SYMBOLS, COST_SYMBOLS, SECURITY_SYMBOLS, COMPLEXITY_SYMBOLS]


class SemanticHeuristic:
    """
    Scores clauses by research promise.
    Penalizes boring arithmetic, rewards cross-domain connections.
    Uses Phantom Hash for deterministic tie-breaking.
    """
    
    CROSS_DOMAIN_BONUS = 0.5
    COMPOSITION_BONUS = 0.3
    ARITHMETIC_PENALTY = -0.3
    REDUCTION_BONUS = 0.4
    ZERO_OPTIMIZATION_BONUS = 0.3 # Build 2.9.0
    IDENTITY_REMOVAL_BONUS = 0.2  # Build 2.9.0
    
    @staticmethod
    def score_clause(clause: Clause) -> float:
        """Score a clause for research promise."""
        score = 1.0
        
        symbols = set()
        for lit in clause.literals:
            symbols |= lit.atom.functions() if hasattr(lit.atom, 'functions') else set()
        
        # Cross-domain bonus
        domains_touched = 0
        for domain_set in ALL_DOMAIN_SETS:
            if symbols & domain_set:
                domains_touched += 1
        if domains_touched >= 2:
            score += SemanticHeuristic.CROSS_DOMAIN_BONUS * (domains_touched - 1)
        
        # Composition bonus
        if symbols & COMPOSITION_SYMBOLS:
            score += SemanticHeuristic.COMPOSITION_BONUS
        
        # Arithmetic penalty
        pure_arithmetic = {"plus", "minus", "times", "zero", "one"}
        if symbols and symbols.issubset(pure_arithmetic):
            score += SemanticHeuristic.ARITHMETIC_PENALTY
        
        # Size penalty (prefer simpler clauses)
        score -= clause.size() * 0.01

        # Build 2.9.0: Optimization detection
        if len(clause.literals) == 1:
            lit = next(iter(clause.literals))
            if isinstance(lit.atom, Equality):
                L, R = lit.atom.left, lit.atom.right
                # Reduction: RHS is smaller than LHS
                if R.size() < L.size():
                    score += SemanticHeuristic.REDUCTION_BONUS
                # Zero-optimization: Eliminates overhead
                if "R_ZERO" in str(R) and "R_ZERO" not in str(L):
                    score += SemanticHeuristic.ZERO_OPTIMIZATION_BONUS
                # Identity removal
                if "ID_M" in str(L) and "ID_M" not in str(R):
                    score += SemanticHeuristic.IDENTITY_REMOVAL_BONUS
        
        # Phantom Noise: Deterministic tie-breaking
        # Hash the clause string representation to get a stable random float [-0.05, 0.05]
        h = phantom_hash(hash(str(clause)), 0, 0, 0)
        noise = ((h & 0xFFFF) / 65536.0) * 0.1 - 0.05
        score += noise
        
        return max(score, 0.01)
    
    @staticmethod
    def score_formula(formula: Formula) -> float:
        """Score a formula for interestingness."""
        symbols = formula.functions()
        score = 1.0
        
        domains_touched = sum(1 for ds in ALL_DOMAIN_SETS if symbols & ds)
        if domains_touched >= 2:
            score += SemanticHeuristic.CROSS_DOMAIN_BONUS * (domains_touched - 1)
        
        if symbols & COMPOSITION_SYMBOLS:
            score += SemanticHeuristic.COMPOSITION_BONUS
        
        return score
