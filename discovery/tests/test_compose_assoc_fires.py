import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.logic import Variable, Function, Equality, MODULE
from discovery.engine import CoAIOperandicsExplorer

def Compose(a, b): return Function("Compose", (a, b), MODULE)

def test_compose_assoc_fires():
    A = Variable("A", MODULE)
    B = Variable("B", MODULE)
    C = Variable("C", MODULE)
    goal = Equality(Compose(Compose(A,B),C), Compose(A,Compose(B,C)))

    explorer = CoAIOperandicsExplorer(certified_mode=True)
    from prover.general_atp import GeneralATP
    from discovery.engine import KnowledgeBase
    kb = KnowledgeBase(axioms=explorer.axioms, theorems=explorer.lemmas, axiom_names=explorer.axiom_names)
    atp = GeneralATP()
    
    res = atp.prove(goal, kb)
    assert res.success, "Proof failed"
    assert "compose_associativity" in res.applied_rules, "compose_associativity rule did not fire"

if __name__ == "__main__":
    test_compose_assoc_fires()
    print("test_compose_assoc_fires passed")
