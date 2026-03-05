"""
core/beta_calculus.py

The β-Calculus: Thermodynamic governance for symbolic discovery.
Bounds combinatorial explosion by assigning a cost (β) to every search step based on surprisal.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class BetaLedger:
    """
    Manages the TensionBudget (β) for a search session.
    Every expansion or rewrite deducts from this budget.
    """
    initial_budget: float = 100.0  # Default β budget
    current_beta: float = field(init=False)
    total_burn: float = 0.0
    
    def __post_init__(self):
        self.current_beta = self.initial_budget

    def deduct(self, amount: float) -> bool:
        """Deducts β from the budget. Returns False if budget exhausted."""
        if self.initial_budget == math.inf:
            self.total_burn += amount
            return True

        if self.current_beta <= 0:
            return False
            
        real_deduction = min(self.current_beta, amount)
        self.current_beta -= real_deduction
        self.total_burn += real_deduction
        return self.current_beta > 0

    @property
    def exhausted(self) -> bool:
        if self.initial_budget == math.inf:
            return False
        return self.current_beta <= 0

    @property
    def ratio(self) -> float:
        """Returns the ratio of remaining budget to initial budget."""
        if self.initial_budget == math.inf:
            return 1.0
        if self.initial_budget <= 0:
            return 0.0
        return self.current_beta / self.initial_budget

    def __repr__(self) -> str:
        if self.initial_budget == math.inf:
            return f"BetaLedger(beta=∞, burn={self.total_burn:.2f})"
        return f"BetaLedger(beta={self.current_beta:.2f}/{self.initial_budget}, burn={self.total_burn:.2f})"

def calculate_surprisal(probability: float, base: float = 2.0) -> float:
    """
    Calculates surprisal (information content) of an event with given probability.
    I(x) = -log_base(P(x))
    """
    if probability <= 0:
        return 10.0  # Cap extreme cost for impossible/near-impossible events
    if probability >= 1.0:
        return 0.0
    return -math.log(probability, base)
