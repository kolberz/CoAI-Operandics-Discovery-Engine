"""
discovery/tests/test_tranche8_integration.py

Verifies the integration of Tranche 8 features:
1. DiscoveryEngine Unified Entry Point
2. Omega Node: Self-Synthesizing Axioms
3. Verifier Equilibrium: Termination Detection
"""

import unittest
import sys
import os

# Ensure we can import from the project root
sys.path.append(os.getcwd())

from discovery.engine import DiscoveryEngine, P_TRUE, PRED
from discovery.liveness import DiscoveryState
from core.logic import MODULE, REAL, Constant, Function, OPERAD_SIGNATURES

class TestTranche8Integration(unittest.TestCase):
    
    def setUp(self):
        # Set small budget and iterations for fast testing
        os.environ["COAI_MCTS_ITERS"] = "10"
        os.environ["COAI_BETA_BUDGET"] = "50.0"
        self.engine = DiscoveryEngine(min_interestingness=0.1)

    def test_omega_invention(self):
        print("\n[Test] Omega Node: Sort/Signature Invention")
        
        # Manually trigger a sort invention
        new_sort_name = self.engine.omega_node.analyze_manifold_divergence(0.95, [1, 2, 3, 4, 5, 6])
        self.assertIsNotNone(new_sort_name)
        self.assertTrue(new_sort_name.startswith("FIELD_"))
        
        new_sort = self.engine.omega_node.invented_sorts[new_sort_name]
        print(f"  Invented Sort: {new_sort}")
        
        # Invent a signature using this sort
        self.engine.omega_node.invent_signature("Interaction", (MODULE, new_sort), REAL)
        self.assertIn("Interaction", OPERAD_SIGNATURES)
        self.assertEqual(OPERAD_SIGNATURES["Interaction"].result_sort, REAL)
        print("  Invented Signature: Interaction(Module, Field) -> Real")

    def test_equilibrium_detection(self):
        print("\n[Test] Verifier Equilibrium Detection")
        from dataclasses import dataclass
        @dataclass
        class MockSession:
            theorems: list
            stats: dict
            
        # Simulate stalls by providing empty discoveries/enodes
        session = MockSession(theorems=[], stats={"new_enodes": 0})
        
        # Should not trigger initially
        self.assertFalse(self.engine.equilibrium_detector.check(session, 0))
        self.assertFalse(self.engine.equilibrium_detector.check(session, 1))
        
        # On the 3rd stall, it should trigger equilibrium
        self.assertTrue(self.engine.equilibrium_detector.check(session, 2))
        print("  Equilibrium detected successfully after 3 stalls.")

    def test_discovery_engine_lifecycle(self):
        print("\n[Test] DiscoveryEngine Unified Lifecycle")
        # Run a short discovery loop
        session = self.engine.discover_and_verify_conjectures(max_cycles=1, verbose=True)
        
        self.assertGreaterEqual(session.stats.get("cycles", 0), 1)
        # Verify backward compatibility
        from discovery.engine import CoAIOperandicsExplorer
        self.assertEqual(DiscoveryEngine, CoAIOperandicsExplorer)
        print("  DiscoveryEngine lifecycle cycle 0 completed.")

if __name__ == "__main__":
    unittest.main()
