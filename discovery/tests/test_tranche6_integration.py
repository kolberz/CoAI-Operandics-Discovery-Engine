"""
discovery/tests/test_tranche6_integration.py

Verifies the integration of Tranche 6 features:
1. Trotter-Suzuki Symmetric Splitting
2. Streaming DPP Diversity Pruning
3. QED Vacuum Polarization (Stressor Fields)
"""

import unittest
import sys
import os
import numpy as np

# Ensure we can import from the project root
sys.path.append(os.getcwd())

from core.logic import Function, Constant, Variable, MODULE, Equality, Forall
from discovery.normalization import normalize_trotter
from discovery.diversity import DiversityPruner
from discovery.mcts_grammar import GrammarSynthesizer

class TestTranche6Integration(unittest.TestCase):
    
    def test_trotter_expansion(self):
        print("\n[Test] Trotter-Suzuki Expansion")
        A = Constant("A", MODULE)
        B = Constant("B", MODULE)
        
        # Trotter(A, B) -> Seq(Half(A), B, Half(A))
        t1 = Function("Trotter", (A, B), MODULE)
        exp1 = normalize_trotter(t1)
        print(f"  Trotter(A, B) expands to: {exp1}")
        
        self.assertEqual(exp1.symbol, "Seq")
        self.assertEqual(len(exp1.args), 3)
        self.assertEqual(exp1.args[0].symbol, "Half")
        self.assertEqual(exp1.args[0].args[0], A)
        self.assertEqual(exp1.args[1], B)
        self.assertEqual(exp1.args[2].symbol, "Half")
        self.assertEqual(exp1.args[2].args[0], A)
        
        # Trotter(A, B, C) -> Seq(Half(A), Trotter(B, C), Half(A))
        # -> Seq(Half(A), Seq(Half(B), C, Half(B)), Half(A))
        C = Constant("C", MODULE)
        t2 = Function("Trotter", (A, B, C), MODULE)
        exp2 = normalize_trotter(t2)
        print(f"  Trotter(A, B, C) expands to: {exp2}")
        self.assertEqual(exp2.args[1].symbol, "Seq")

    def test_dpp_diversity(self):
        print("\n[Test] Streaming DPP Pruning")
        pruner = DiversityPruner(threshold=0.2)
        
        A = Constant("A", MODULE)
        B = Constant("B", MODULE)
        
        # Identity 1: Half(A) = Half(A)
        f1 = Function("Half", (A,), MODULE)
        # Identity 2: Half(B) = Half(B) (Diverse from f(A))
        f2 = Function("Half", (B,), MODULE)
        # Identity 3: Half(A) = Half(A) (Redundant)
        f3 = Function("Half", (A,), MODULE)
        
        self.assertTrue(pruner.should_keep(f1))
        self.assertTrue(pruner.should_keep(f2))
        self.assertFalse(pruner.should_keep(f3))
        print(f"  Kept 1: {f1}")
        print(f"  Kept 2: {f2}")
        print(f"  Kept 3: {f3} -> (Pruned as expected)")

    def test_qed_stressor_fields(self):
        print("\n[Test] QED Stressor Fields (Novelty Bias)")
        from discovery.scorer import InterestingnessScorer
        
        class MockScorer(InterestingnessScorer):
            def score(self, formula): return 0.5
            
        synth = GrammarSynthesizer(MockScorer())
        
        # Initial run: populate history
        print("  Running MCTS initial pass...")
        forms1, asts1 = synth.synthesize(iterations=200)
        initial_history_size = len(synth.history)
        print(f"  Initial history nodes: {initial_history_size}")
        
        # Second run: check if it explores NEW nodes
        print("  Running MCTS biased pass...")
        # We'll run it manually for one iteration to see if it adds anything
        initial_history_content = set(synth.history)
        forms2, asts2 = synth.synthesize(iterations=200)
        final_history_size = len(synth.history)
        
        new_nodes = set(synth.history) - initial_history_content
        print(f"  Final history nodes: {final_history_size}")
        print(f"  New nodes explored: {len(new_nodes)}")
        
        # If it didn't grow, let's see some samples of what's in there
        if len(new_nodes) == 0:
            print("  [DEBUG] History samples:")
            for h in list(synth.history)[:5]:
                print(f"    - {h}")
        
        # We expect history to grow significantly because of the novelty bias
        self.assertTrue(final_history_size > initial_history_size)

if __name__ == "__main__":
    unittest.main()
