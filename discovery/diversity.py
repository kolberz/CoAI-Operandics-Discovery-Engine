"""
discovery/diversity.py

Implements Streaming DPP (Determinantal Point Process) Pruning for discovered theorems.
Ensures the theorem ensemble is structurally diverse.
"""

import math
import numpy as np
from typing import List, Set, Any
from core.logic import Term, Function, Constant, Variable

class DiversityPruner:
    """
    Greedy DPP-based pruner for structural diversity.
    Uses a bag-of-symbols kernel to estimate similarity.
    """
    def __init__(self, threshold: float = 0.01):
        self.selected_vectors: List[np.ndarray] = []
        self.threshold = threshold
        self.all_symbols: List[str] = []
        self.symbol_to_idx: dict[str, int] = {}

    def _get_symbols(self, term: Term) -> Set[str]:
        if isinstance(term, (Variable, Constant)):
            return {str(term)}
        if isinstance(term, Function):
            res = {term.symbol}
            for a in term.args:
                res |= self._get_symbols(a)
            return res
        return set()

    def _term_to_vector(self, term: Term) -> np.ndarray:
        symbols = self._get_symbols(term)
        # Dynamic symbol registry expansion
        for s in symbols:
            if s not in self.symbol_to_idx:
                self.symbol_to_idx[s] = len(self.all_symbols)
                self.all_symbols.append(s)
        
        vec = np.zeros(len(self.all_symbols))
        for s in symbols:
            vec[self.symbol_to_idx[s]] = 1.0
        return vec

    def _pad_vectors(self):
        """Ensure all selected vectors have the same dimension as all_symbols."""
        dim = len(self.all_symbols)
        for i in range(len(self.selected_vectors)):
            if len(self.selected_vectors[i]) < dim:
                self.selected_vectors[i] = np.pad(self.selected_vectors[i], (0, dim - len(self.selected_vectors[i])))

    def should_keep(self, term: Term) -> bool:
        """
        Returns True if the term adds sufficient diversity (orthogonal component).
        """
        vec = self._term_to_vector(term)
        self._pad_vectors()
        
        if not self.selected_vectors:
            self.selected_vectors.append(vec)
            return True
        
        # Greedy DPP-style: find the component of 'vec' orthogonal to the span of selected_vectors
        # We use a simplified version: find distance to the nearest neighbor or use projection
        # For a true DPP, we'd look at the determinant increase, but for binary vectors,
        # we can just use 1 - max(cosine_sim).
        
        max_sim = 0.0
        for s_vec in self.selected_vectors:
            norm_s = np.linalg.norm(s_vec)
            norm_v = np.linalg.norm(vec)
            if norm_s > 0 and norm_v > 0:
                sim = np.dot(s_vec, vec) / (norm_s * norm_v)
                max_sim = max(max_sim, sim)
        
        if (1.0 - max_sim) >= self.threshold:
            self.selected_vectors.append(vec)
            return True
        
        return False

    def prune_list(self, terms: List[Any], key_fn: Any = lambda x: x) -> List[Any]:
        """Filters a list of objects (e.g. DiscoveredTheorem) for diversity."""
        kept = []
        for item in terms:
            if self.should_keep(key_fn(item)):
                kept.append(item)
        return kept
