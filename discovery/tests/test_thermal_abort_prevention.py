"""
discovery/tests/test_thermal_abort_prevention.py

Verifies that the BetaGate correctly triggers steering 
before thermodynamic exhaustion (BetaLedger depletion).
"""

import unittest
import sys
import os

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from discovery.tools.corridor import LatentState, BetaGate, Corridor, Orchestrator, Regime

class TestThermalAbortPrevention(unittest.TestCase):
    def test_beta_gate_violation_and_steering(self):
        # 1. Setup BetaGate with 10% threshold
        beta_gate = BetaGate(min_budget_ratio=0.10, epsilon=0.05)
        corridor = Corridor([beta_gate])
        orchestrator = Orchestrator(corridor, risk_budget=0.1)
        
        # 2. State with healthy budget (50%)
        state_healthy = LatentState(
            entropy=1.0, 
            attention_coherence=0.9, 
            embedding_norm=10.0, 
            manifold_divergence=0.1, 
            centroid_similarity=0.9,
            tension_budget_ratio=0.5
        )
        outcome1 = orchestrator.observe(state_healthy)
        self.assertTrue(outcome1.snapshot.in_corridor)
        self.assertEqual(outcome1.snapshot.regime, Regime.CORRIDOR)
        
        # 3. State with near-exhausted budget (5%)
        # This should trigger the BetaGate
        state_crit = LatentState(
            entropy=1.0, 
            attention_coherence=0.9, 
            embedding_norm=10.0, 
            manifold_divergence=0.1, 
            centroid_similarity=0.9,
            tension_budget_ratio=0.05
        )
        outcome2 = orchestrator.observe(state_crit)
        
        print(f"Outcome 2 regime: {outcome2.snapshot.regime}")
        print(f"Outcome 2 recovered: {outcome2.recovered}")
        print(f"Outcome 2 final ratio: {outcome2.state.tension_budget_ratio}")
        
        # The orchestrator should have seen the violation and attempted steering
        # Even if it didn't fully recover to > 10% in one step, it should have 
        # MOVED the ratio UPWARDS toward the inset.
        self.assertTrue(outcome2.state.tension_budget_ratio > 0.05)
        self.assertTrue(outcome2.recovered) # Should recover because BetaGate project is simple

if __name__ == "__main__":
    unittest.main()
