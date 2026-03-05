"""
discovery/tests/test_beta_exhaustion_halts.py

Verifies that the beta-Calculus correctly halts MCTS search when the budget is exhausted.
"""

import unittest
import sys
import os

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from discovery.engine import CoAIOperandicsExplorer
from core.beta_calculus import BetaLedger

class TestBetaExhaustion(unittest.TestCase):
    def test_exhaustion_halting(self):
        # Set a very low budget and high iterations
        os.environ["COAI_MCTS_ITERS"] = "10000"
        os.environ["COAI_BETA_BUDGET"] = "5.0"
        
        explorer = CoAIOperandicsExplorer()
        
        print(f"Initial Budget: {explorer.beta_ledger}")
        
        # Run conjecture generation (which triggers MCTS)
        explorer.conjecture_new_axioms([])
        
        print(f"Final Budget: {explorer.beta_ledger}")
        
        # The budget should be exhausted or very close to it
        self.assertTrue(explorer.beta_ledger.exhausted or explorer.beta_ledger.current_beta < 1.0)
        self.assertTrue(explorer.beta_ledger.total_burn > 0)
        print("SUCCESS: beta-Calculus halted search upon exhaustion.")

if __name__ == "__main__":
    unittest.main()
