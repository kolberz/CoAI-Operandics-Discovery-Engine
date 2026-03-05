
import sys
import os
sys.path.append(os.getcwd())

from core.logic import Variable, Function, Equality, MODULE, REAL, Forall
from discovery.normalization import (
    RiskEGraph, ERewrite, saturate_with_rewrites, logic_to_egraph_term
)
from prover.general_atp import GeneralProver

def test_normalization():
    print("--- Testing E-Graph Normalization ---")
    egraph = RiskEGraph()
    
    # 1. Identity Verification
    # Forall M. Risk(Seq(M, ID_M)) = Risk(M)
    M = Variable("M")
    ID_M = Function("ID_M", (), MODULE)
    Risk = lambda x: Function("Risk", (x,), REAL)
    Seq = lambda x, y: Function("Seq", (x, y), MODULE)
    
    lhs = Risk(Seq(M, ID_M))
    rhs = Risk(M)
    
    # Define rewrite: Risk(Seq(VAR_M, ID_M)) -> Risk(VAR_M)
    # Using the egraph logic conversion
    rewrites = [
        ERewrite(
            logic_to_egraph_term(lhs),
            logic_to_egraph_term(rhs),
            "identity"
        )
    ]
    
    l_id = egraph.add(logic_to_egraph_term(lhs))
    r_id = egraph.add(logic_to_egraph_term(rhs))
    
    print(f"Initial: Find(L)={egraph.find(l_id)}, Find(R)={egraph.find(r_id)}")
    saturate_with_rewrites(egraph, rewrites)
    print(f"After Saturation: Find(L)={egraph.find(l_id)}, Find(R)={egraph.find(r_id)}")
    
    if egraph.find(l_id) == egraph.find(r_id):
        print("[PASS] Identity proved via E-Graph.")
    else:
        print("[FAIL] Identity proof failed.")

def test_associativity():
    print("\n--- Testing Associativity Verification ---")
    egraph = RiskEGraph()
    
    A = Variable("A")
    B = Variable("B")
    C = Variable("C")
    Par = lambda x, y: Function("Par_Dyn", (x, y), MODULE)
    Risk = lambda x: Function("Risk", (x,), REAL)
    
    # Risk(Par(A, Par(B, C))) = Risk(Par(Par(A, B), C))
    t1 = Risk(Par(A, Par(B, C)))
    t2 = Risk(Par(Par(A, B), C))
    
    rewrites = [
        ERewrite(
            logic_to_egraph_term(Par(A, Par(B, C))),
            logic_to_egraph_term(Par(Par(A, B), C)),
            "assoc"
        )
    ]
    
    id1 = egraph.add(logic_to_egraph_term(t1))
    id2 = egraph.add(logic_to_egraph_term(t2))
    
    saturate_with_rewrites(egraph, rewrites)
    
    if egraph.find(id1) == egraph.find(id2):
        print("[PASS] Associativity proved via E-Graph.")
    else:
        print("[FAIL] Associativity proof failed.")

def test_contextual_congruence():
    print("\n--- Testing Contextual Congruence (C-1) ---")
    egraph = RiskEGraph()
    
    A = Variable("A")
    B = Variable("B")
    C = Variable("C")
    Risk = lambda x: Function("Risk", (x,), REAL)
    Par = lambda x, y: Function("Par_Dyn", (x, y), MODULE)
    
    # Rule: Risk(A) = Risk(B)  (e.g. from some lemma)
    # Goal: Risk(Par(C, A)) = Risk(Par(C, B))
    
    r_a_id = egraph.add(logic_to_egraph_term(Risk(A)))
    r_b_id = egraph.add(logic_to_egraph_term(Risk(B)))
    
    # Add target terms to graph so they are indexed
    target_a_id = egraph.add(logic_to_egraph_term(Risk(Par(C, A))))
    target_b_id = egraph.add(logic_to_egraph_term(Risk(Par(C, B))))
    
    print(f"Pre-Union: Find(TargetA)={egraph.find(target_a_id)}, Find(TargetB)={egraph.find(target_b_id)}")
    
    # Stipulate Risk(A) = Risk(B)
    egraph.union(r_a_id, r_b_id)
    
    # Close C-1
    egraph.close_contextual_congruence()
    
    print(f"After C-1: Find(TargetA)={egraph.find(target_a_id)}, Find(TargetB)={egraph.find(target_b_id)}")
    
    if egraph.find(target_a_id) == egraph.find(target_b_id):
        print("[PASS] C-1 Contextual Congruence proved via E-Graph.")
    else:
        print("[FAIL] C-1 logic failed.")

if __name__ == "__main__":
    test_normalization()
    test_associativity()
    test_contextual_congruence()
    
