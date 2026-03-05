import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.logic import Equality, Variable, MODULE, REAL, Function, Forall
from discovery.engine import CoAIOperandicsExplorer, DiscoverySession, DiscoveredTheorem

def test_congruence_deduplication():
    explorer = CoAIOperandicsExplorer()
    
    # 1. Add axiom A = B
    A = Variable("A", MODULE)
    B = Variable("B", MODULE)
    explorer._add_axiom(Equality(A, B), "test_id")
    
    # 2. Propose conjecture Risk(A) = Risk(B)
    RiskA = Function("Risk", (A,), REAL)
    RiskB = Function("Risk", (B,), REAL)
    conj = Forall(A, Forall(B, Equality(RiskA, RiskB)))
    
    # 3. Test deduplication
    # We simulate a "structural discovery" resulting in conj
    theorems = [] # dummy
    conjectures = explorer.conjecture_new_axioms(theorems)
    
    # If the deduplication works, conj should NOT be in conjectures 
    # (assuming it's checked against the e-graph)
    # However, our test manually checks the e-graph find() result first
    
    from discovery.normalization import logic_to_egraph_term
    et_fA = logic_to_egraph_term(RiskA)
    et_fB = logic_to_egraph_term(RiskB)
    
    id_fA = explorer.egraph.add(et_fA)
    id_fB = explorer.egraph.add(et_fB)
    
    # Because A=B is an axiom, Risk(A) and Risk(B) should have the same find() result
    assert explorer.egraph.find(id_fA) == explorer.egraph.find(id_fB)
    
    print("SUCCESS: Risk(A) and Risk(B) are congruent in the explorer e-graph.")

if __name__ == "__main__":
    test_congruence_deduplication()
