"""
Experiment 4: E-Graph vs Standard ATP Scaling
================================================
Measures the number of steps and Wall-clock time to prove deeply nested 
associative constraints using Standard Resolution vs E-Graph Normalization.

This verifies the thesis that E-Graphs provide O(1) or near-linear scaling 
for structural equivalence, whereas Standard ATP degrades exponentially.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logic import *
from prover.general_atp import GeneralProver
import time
from tabulate import tabulate

def create_nested_seq(depth, a_var, b_var):
    """Creates a right-leaning nested Seq term."""
    if depth == 1:
        return Function("Seq", (a_var, b_var), MODULE)
    return Function("Seq", (a_var, create_nested_seq(depth - 1, a_var, b_var)), MODULE)

def create_left_nested_seq(depth, a_var, b_var):
    """Creates a left-leaning nested Seq term."""
    if depth == 1:
        return Function("Seq", (a_var, b_var), MODULE)
    return Function("Seq", (create_left_nested_seq(depth - 1, a_var, b_var), b_var), MODULE)

def run_scaling_benchmark():
    print("==========================================================")
    print(" Experiment 4: ATP vs E-Graph Congruence Scaling Wall ")
    print("==========================================================")
    
    m1 = Variable("M1", MODULE)
    m2 = Variable("M2", MODULE)
    m3 = Variable("M3", MODULE)
    
    # Base axioms
    ax_assoc = Forall(m1, Forall(m2, Forall(m3,
        Equality(
            Function("Seq", (Function("Seq", (m1, m2), MODULE), m3), MODULE),
            Function("Seq", (m1, Function("Seq", (m2, m3), MODULE)), MODULE)
        )
    )))
    
    max_depth = 5
    results = []
    
    for depth in range(2, max_depth + 1):
        print(f"\nEvaluating nesting depth {depth}...")
        
        target_a = create_left_nested_seq(depth, m1, m2)
        target_b = create_nested_seq(depth, m1, m2)
        goal = Equality(target_a, target_b)
        
        # 1. Standard ATP
        prover_std = GeneralProver()
        prover_std.add_axiom(ax_assoc)
        # Disable E-graph
        prover_std._egraph_normalization_enabled = False 
        
        t0 = time.time()
        res_std = prover_std.prove(goal, max_steps=1000, timeout_seconds=10.0)
        t_std = time.time() - t0
        
        # 2. E-Graph ATP
        prover_eg = GeneralProver()
        prover_eg.add_axiom(ax_assoc)
        prover_eg._egraph_normalization_enabled = True
        
        t0 = time.time()
        res_eg = prover_eg.prove_with_normalization(goal, lemmas=[ax_assoc], max_steps=1000)
        t_eg = time.time() - t0
        
        results.append([
            depth, 
            f"{res_std.steps} steps" if res_std.success else "TIMEOUT", 
            f"{t_std*1000:.1f} ms",
            "O(1) EG" if res_eg.reason == "EGRAPH_NORMALIZATION" else f"{res_eg.steps} steps",
            f"{t_eg*1000:.1f} ms"
        ])
        
    print("\n" + "="*60)
    print(tabulate(results, headers=["Depth", "Std Steps", "Std Time", "E-Graph Steps", "EG Time"]))
    print("="*60)
    
if __name__ == "__main__":
    try:
        import tabulate as _tab
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tabulate"])
    run_scaling_benchmark()
