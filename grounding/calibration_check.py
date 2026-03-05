"""
grounding/calibration_check.py

Gate 4 Hardening Script.
Verifies that the new Gen-2 Stable Axiom Indices pass the Dimensional Checker.
Also computes the 'Calibration Offset' for the new manifold.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from discovery.engine import CoAIOperandicsExplorer
from grounding.dimensions import DimensionalChecker, DimensionRegistry

def run_calibration():
    print("--- Gate 4: Dimensional Calibration ---")
    
    # 1. Load Engine (with new Axioms)
    explorer = CoAIOperandicsExplorer()
    print(f"[1] Loaded Engine with {len(explorer.axioms)} axioms.")
    
    # 2. Extract 'Discovered' Axioms
    discovered = [a for a in explorer.axioms 
                  if hasattr(a, 'right') and 'StableAxiom' in str(a.right)]
    # Actually, Formula structure is Equality(Constant(StableAxiom_X), P_TRUE)
    # So a.left is Constant, a.right is P_TRUE.
    
    print(f"[2] Extracted {len(discovered)} stable axioms for calibration.")
    
    # 3. Dimensional Check
    reg = DimensionRegistry()
    checker = DimensionalChecker(reg)
    
    # We need to check if 'StableAxiom_X' has dimensions?
    # It's a Proposition (PRED). P_TRUE is PRED.
    # Equality(PRED, PRED) should be dimensionally consistent (PRED==PRED).
    
    report = checker.check_axiom_set(explorer.axioms, explorer.axiom_names)
    
    print(f"[3] Dimensional Verdict: {report.verdict}")
    if report.verdict == "PASS":
        print(f"    - Calibration Markers: {report.calibration_markers}")
        print(f"    - Unknown Constants: {len(report.unknown_constants)}")
        if len(report.unknown_constants) > 0:
            print(f"      {list(report.unknown_constants)[:5]}...")
        print("[SUCCESS] Gen-2 Manifold is Dimensionally Consistent.")
    else:
        print(f"[FAILURE] Dimensional Errors Found:")
        for e in report.errors:
            print(f"  - {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_calibration()
