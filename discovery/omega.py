"""
discovery/omega.py

The Omega Node: Self-Synthesizing Axioms.
Allows the engine to autonomously extend its own logical foundation.
"""

from typing import List, Tuple, Optional, Dict, Any, Set
from core.logic import (
    register_sort, register_signature, 
    Sort, Term, Function, Constant, Variable, 
    MODULE, REAL, PROB
)

class OmegaSynthesizer:
    """
    Inverts the discovery relationship: instead of theorems from axioms,
    it synthesizes new sorts and signatures to explain novel patterns.
    """
    def __init__(self):
        self.invented_sorts: Dict[str, Sort] = {}
        self.invented_symbols: Set[str] = set()

    def invent_sort(self, name: str) -> Sort:
        """Dynamically extends the sort lattice."""
        if name not in self.invented_sorts:
            s = register_sort(name)
            self.invented_sorts[name] = s
        return self.invented_sorts[name]

    def invent_signature(self, symbol: str, arg_sorts: Tuple[Sort, ...], result_sort: Sort, variadic: bool = False):
        """Dynamically extends the signature registry."""
        if symbol not in self.invented_symbols:
            register_signature(symbol, arg_sorts, result_sort, variadic)
            self.invented_symbols.add(symbol)

    def analyze_manifold_divergence(self, divergence_score: float, top_theorems: List[Any]) -> Optional[str]:
        """
        If divergence is high, suggest a new 'Physics Field' sort to 
        explain the residual complexity.
        """
        if divergence_score > 0.9 and len(top_theorems) > 5:
            # Suggest a new sort name based on the most common symbols
            new_sort_name = f"FIELD_{len(self.invented_sorts)}"
            self.invent_sort(new_sort_name)
            return new_sort_name
        return None
