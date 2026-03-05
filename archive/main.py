"""
main.py

Entry point for the CoAI Operandics Discovery Engine.
"""

from discovery.engine import CoAIOperandicsExplorer, DiscoverySession
from core.logic import *
from prover.general_atp import GeneralATP
from discovery.engine import KnowledgeBase
import time


def run_basic_proof_test():
    """Verify the prover works on simple cases."""
    print("="*60)
    print("  PROVER SELF-TEST")
    print("="*60)
    
    prover = GeneralATP()
    kb = KnowledgeBase()
    
    m1 = Variable("M1", MODULE)
    m2 = Variable("M2", MODULE)
    
    def Seq(a, b): return Function("Seq", (a, b), MODULE)
    def Risk(m): return Function("Risk", (m,), REAL)
    def plus(a, b): return Function("plus", (a, b), REAL)
    
    ID_M = Constant("ID_M", MODULE)
    R_ZERO = Constant("R_ZERO", REAL)
    
    # Add axioms
    kb.axioms.append(Forall(m1, Equality(Seq(m1, ID_M), m1)))
    kb.axioms.append(Forall(m1, Forall(m2,
        Equality(Risk(Seq(m1, m2)), plus(Risk(m1), Risk(m2)))
    )))
    kb.axioms.append(Equality(Risk(ID_M), R_ZERO))
    kb.axioms.append(Forall(m1, Equality(plus(m1, R_ZERO), m1)))
    
    # Test 1: Risk(Seq(M1, ID_M)) = Risk(M1)
    test_var = Variable("X", MODULE)
    goal = Equality(Risk(Seq(test_var, ID_M)), Risk(test_var))
    
    print(f"\n  Test 1: {goal}")
    result = prover.prove(goal, kb)
    print(f"  Result: {'PROVED' if result.success else 'FAILED'} in {result.steps} steps")
    print(f"  Reason: {result.reason}")
    
    # Test 2: Should fail — Seq is not commutative (no such axiom)
    goal2 = Forall(m1, Forall(m2, Equality(Seq(m1, m2), Seq(m2, m1))))
    print(f"\n  Test 2 (should fail): Seq commutativity")
    result2 = prover.prove(goal2, kb)
    print(f"  Result: {'PROVED' if result2.success else 'FAILED'} in {result2.steps} steps")
    print(f"  Reason: {result2.reason}")
    
    return result.success and not result2.success


def run_discovery():
    """Run the full discovery engine."""
    print("\n" + "="*60)
    print("  CoAI OPERANDICS DISCOVERY ENGINE")
    print("="*60)
    
    explorer = CoAIOperandicsExplorer(
        max_clauses=400,
        max_depth=6,
        min_interestingness=0.15
    )
    
    print(f"\n  Initialized with {len(explorer.axioms)} axioms")
    print(f"  Starting cumulative discovery loop (5 cycles)...")
    
    session = explorer.discover_and_verify_conjectures(
        cumulative=True,
        max_cycles=5,
        verbose=True
    )
    
    explorer.report(session)
    
    return session


def run_targeted_proofs():
    """Attempt to prove specific theorems from the catalog."""
    print("\n" + "="*60)
    print("  TARGETED THEOREM VERIFICATION")
    print("="*60)
    
    explorer = CoAIOperandicsExplorer()
    
    prover = GeneralATP()
    kb = KnowledgeBase(axioms=explorer.axioms)
    
    m1 = Variable("M1", MODULE)
    m2 = Variable("M2", MODULE)
    
    targets = []
    
    # Target 1: Risk(Seq(M1, ID_M)) = Risk(M1) [from axioms]
    targets.append((
        "Risk Identity Simplification",
        Forall(m1, Equality(
            Function("Risk", (Function("Seq", (m1, Constant("ID_M", MODULE)), MODULE),), REAL),
            Function("Risk", (m1,), REAL)
        ))
    ))
    
    # Target 2: Par_Dyn self-composition risk
    targets.append((
        "Parallel Self-Composition Idempotency",
        Forall(m1, Equality(
            Function("Risk", (Function("Par_Dyn", (m1, m1), MODULE),), REAL),
            Function("Risk", (m1,), REAL)
        ))
    ))
    
    # Target 3: Parallel Commutativity
    targets.append((
        "Parallel Commutativity",
        Forall(m1, Forall(m2, Equality(
            Function("Par_Dyn", (m1, m2), MODULE),
            Function("Par_Dyn", (m2, m1), MODULE)
        )))
    ))
    
    # Target 4: Sequential Associativity
    m3 = Variable("M3", MODULE)
    targets.append(("Seq Associativity",
        Forall(m1, Forall(m2, Forall(m3,
            Equality(
                Function("Seq", (Function("Seq", (m1, m2), MODULE), m3), MODULE),
                Function("Seq", (m1, Function("Seq", (m2, m3), MODULE)), MODULE)
            )
        )))
    ))

    # Target 5: Risk of Identity
    targets.append(("Risk(ID_M) = 0",
        Equality(Function("Risk", (Constant("ID_M", MODULE),), REAL), Constant("R_ZERO", REAL))
    ))

    # Target 6: Trivial Barrier
    targets.append(("Trivial Barrier has no penalty",
        Forall(m1, Equality(
            Function("Risk", (Function("Barrier", (m1, Constant("P_TRUE", PRED)), MODULE),), REAL),
            Function("Risk", (m1,), REAL)
        ))
    ))

    # Target 7: Security Bottleneck
    targets.append(("Security Bottleneck",
        Forall(m1, Forall(m2,
            Equality(
                Function("Ent", (Function("Seq", (m1, m2), MODULE),), REAL),
                Function("min", (Function("Ent", (m1,), REAL), Function("Ent", (m2,), REAL)), REAL)
            )
        ))
    ))

    # Target 8: Cost Identity Simplification
    targets.append(("Cost(Seq(M, ID)) = Cost(M)",
        Forall(m1, Equality(
            Function("ResourceCost", (Function("Seq", (m1, Constant("ID_M", MODULE)), MODULE),), REAL),
            Function("ResourceCost", (m1,), REAL)
        ))
    ))

    # Target 9: Entropy Identity Simplification  
    targets.append(("Ent(Seq(M, ID)) = Ent(M)",
        Forall(m1, Equality(
            Function("Ent", (Function("Seq", (m1, Constant("ID_M", MODULE)), MODULE),), REAL),
            Function("Ent", (m1,), REAL)
        ))
    ))

    # Target 10: Parallel cost <= sequential cost
    targets.append(("Par cost <= Seq cost",
        Forall(m1, Forall(m2,
            LessEq(
                Function("ResourceCost", (Function("Par_Dyn", (m1, m2), MODULE),), REAL),
                Function("ResourceCost", (Function("Seq", (m1, m2), MODULE),), REAL)
            )
        ))
    ))
    
    for name, goal in targets:
        print(f"\n  Target: {name}")
        print(f"  Formula: {goal}")
        result = prover.prove(goal, kb)
        status = "[OK] PROVED" if result.success else f"[FAIL] FAILED ({result.reason})"
        print(f"  Result: {status} in {result.steps} steps")


if __name__ == "__main__":
    start = time.time()
    
    print("\n" + "="*60)
    print("  CoAI OPERANDICS DISCOVERY ENGINE v2.0")
    print("  Enhanced: Congruence | Deduplication | Diverse Conjectures")
    print("="*60)
    
    # Phase 1: Verify the prover works
    prover_ok = run_basic_proof_test()
    print(f"\n  Prover self-test: {'PASSED' if prover_ok else 'FAILED'}")
    
    # Phase 2: Attempt targeted theorem proofs
    run_targeted_proofs()
    
    # Phase 3: Run the full discovery loop
    session = run_discovery()
    
    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  Total runtime: {elapsed:.1f}s")
    print(f"  Theorems discovered: {len(session.theorems)}")
    print(f"  Counter-axioms: {len(session.counter_axioms)}")
    print(f"  Oracle axioms: {len(session.oracle_axioms)}")
    print(f"{'='*60}")
