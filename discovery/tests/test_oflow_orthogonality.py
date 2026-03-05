"""
discovery/tests/test_oflow_orthogonality.py

Verifies O-FLOW sorting:
Phase 1 (Topological) should never produce results with REAL/PROB sorts.
"""

import unittest
import sys
import os

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from core.logic import *
from discovery.saturator import ForwardChainingSaturator

class TestOFlowOrthogonality(unittest.TestCase):
    def test_topological_purity(self):
        # Axioms with mix of sorts
        m1 = Variable("M1", MODULE)
        m2 = Variable("M2", MODULE)
        r1 = Variable("R1", REAL)
        
        axioms = [
            # Topo rule
            Forall(m1, Forall(m2, Equality(Function("Seq", (m1, m2), MODULE), Function("Seq", (m2, m1), MODULE)))),
            # Algebraic rule
            Forall(m1, Equality(Function("Risk", (m1,), REAL), r1))
        ]
        
        saturator = ForwardChainingSaturator(mode="topological")
        result = saturator.saturate(axioms)
        
        print(f"Topological results: {result.generated_equalities}")
        
        # All results must be purely topological (MODULE sort)
        for eq in result.generated_equalities:
            self.assertEqual(eq.left.sort, MODULE)
            self.assertEqual(eq.right.sort, MODULE)
            # Ensure no REAL functions leaked in
            self.assertFalse("Risk" in str(eq))
            
    def test_algebraic_inclusion(self):
        m1 = Variable("M1", MODULE)
        r1 = Variable("R1", REAL)
        r2 = Variable("R2", REAL)
        
        axioms = [
            # Algebraic rule
            Forall(r1, Forall(r2, Equality(Function("add", (r1, r2), REAL), Function("add", (r2, r1), REAL))))
        ]
        
        # In topological mode, this should be ignored
        sat_topo = ForwardChainingSaturator(mode="topological")
        res_topo = sat_topo.saturate(axioms)
        self.assertEqual(len(res_topo.generated_equalities), 0)
        
        # In full/algebraic mode, it should be present
        sat_full = ForwardChainingSaturator(mode="full")
        res_full = sat_full.saturate(axioms)
        self.assertTrue(len(res_full.generated_equalities) > 0)
        print(f"Full mode results: {res_full.generated_equalities}")

if __name__ == "__main__":
    unittest.main()
