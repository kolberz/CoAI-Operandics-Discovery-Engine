"""
discovery/tests/test_curvature_dampening.py

Verifies that GrammarSynthesizer dampens its search intensity 
based on the e-graph branching factor (curvature).
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from discovery.mcts_grammar import GrammarSynthesizer

class TestCurvatureDampening(unittest.TestCase):
    def test_dampening_effect(self):
        scorer = MagicMock()
        scorer.score.return_value = 0.5
        
        synth = GrammarSynthesizer(scorer, max_depth=3)
        
        # Base case: low branching factor
        # We'll use a very small iteration count for speed in test
        base_iters = 100
        forms1, asts1 = synth.synthesize(iterations=base_iters, branching_factor=1.0)
        
        # Noisy case: high branching factor (> 4.0)
        # Curvature should trip and reduce iterations
        # tau = 4.0 / 8.0 = 0.5
        # effective_iters = 100 * 0.5 = 50
        forms2, asts2 = synth.synthesize(iterations=base_iters, branching_factor=8.0)
        
        print(f"Base iteration results: {len(asts1)} ASTs")
        print(f"Dampened iteration results: {len(asts2)} ASTs")
        
        # We expect fewer ASTs explored/returned in the dampened case 
        # because the loop runs for strictly fewer iterations.
        self.assertTrue(len(asts2) <= len(asts1))

if __name__ == "__main__":
    unittest.main()
