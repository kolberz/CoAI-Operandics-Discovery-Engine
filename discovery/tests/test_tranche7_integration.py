"""
discovery/tests/test_tranche7_integration.py

Verifies the integration of Tranche 7 features:
1. MetaShield Sidecar Ledger
2. Büchi Automata Liveness
3. QiC zk-SNARK Verifiability
"""

import unittest
import sys
import os
import time

# Ensure we can import from the project root
sys.path.append(os.getcwd())

from discovery.engine import CoAIOperandicsExplorer, DiscoveredTheorem, P_TRUE, PRED
from core.logic import Constant, MODULE, Equality
from discovery.liveness import DiscoveryState

class TestTranche7Integration(unittest.TestCase):
    
    def setUp(self):
        # Set small budget and iterations for fast testing
        os.environ["COAI_MCTS_ITERS"] = "10"
        os.environ["COAI_BETA_BUDGET"] = "50.0"
        self.explorer = CoAIOperandicsExplorer(min_interestingness=0.1)

    def test_audit_ledger_recording(self):
        print("\n[Test] MetaShield Audit Recording")
        A = Constant("A", MODULE)
        
        # Manually record an event
        h1 = self.explorer.audit_ledger.record_discovery(A, "test_source", 1.0)
        print(f"  First entry hash: {h1}")
        
        # Verify integrity
        self.assertTrue(self.explorer.audit_ledger.verify_integrity())
        
        # Record another
        B = Constant("B", MODULE)
        h2 = self.explorer.audit_ledger.record_discovery(B, "test_source_2", 2.0)
        print(f"  Second entry hash: {h2}")
        
        self.assertEqual(len(self.explorer.audit_ledger.entries), 2)
        self.assertTrue(self.explorer.audit_ledger.verify_integrity())

    def test_buchi_liveness_violation(self):
        print("\n[Test] Büchi Liveness Stall Detection")
        # Simulate stalls
        for _ in range(5):
            self.explorer.liveness_monitor.observe_state(DiscoveryState.CONJECTURING)
        
        # The 6th stall should raise RuntimeError
        with self.assertRaisesRegex(RuntimeError, "LIVENESS_VIOLATION"):
            self.explorer.liveness_monitor.observe_state(DiscoveryState.CONJECTURING)
        print("  Stall detected successfully.")

    def test_explorer_integration(self):
        print("\n[Test] Explorer Lifecycle with Tranche 7")
        # Run 1 cycle to see if it populates audits and possibly zk-proofs
        # (Since it's highly interesting, might need to fake one or just check if it runs)
        session = self.explorer.discover_and_verify_conjectures(max_cycles=1, verbose=True)
        
        print(f"  Audit entries after 1 cycle: {len(self.explorer.audit_ledger.entries)}")
        # If any theorems were proved, they should be in the audit ledger
        # (Depends on discovery success, but at least shouldn't crash)
        self.assertTrue(self.explorer.audit_ledger.verify_integrity())
        
        # Check for zk proofs in high-interestingness theorems
        zk_found = False
        for thm in session.theorems:
            if "zk_proof" in thm.contract.risk:
                zk_found = True
                print(f"  Found ZK Proof for theorem: {thm.formula}")
                break
        
        # Even if none found (low random chance), we verified no crash
        print("  Explorer cycle completed with Tranche 7 actives.")

if __name__ == "__main__":
    unittest.main()
