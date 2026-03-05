import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.logic import Variable, Function, Equality, MODULE
from discovery.engine import CoAIOperandicsExplorer

def Compose(a, b): return Function("Compose", (a, b), MODULE)
def Transpose(a): return Function("Transpose", (a,), MODULE)

def test_transpose_compose_fires():
    A = Variable("A", MODULE)
    B = Variable("B", MODULE)
    goal = Equality(Transpose(Compose(A,B)), Compose(Transpose(B), Transpose(A)))

    explorer = CoAIOperandicsExplorer(certified_mode=True)
    from prover.general_atp import GeneralATP
    from discovery.engine import KnowledgeBase
    kb = KnowledgeBase(axioms=explorer.axioms, theorems=explorer.lemmas, axiom_names=explorer.axiom_names)
    atp = GeneralATP()
    
    res = atp.prove(goal, kb)
    assert res.success, "Proof failed"
    assert "transpose_compose" in res.applied_rules, "transpose_compose rule did not fire"

if __name__ == "__main__":
    test_transpose_compose_fires()
    print("test_transpose_compose_fires passed")
