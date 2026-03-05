import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.logic import Variable, Function, Equality, MODULE
from discovery.engine import CoAIOperandicsExplorer

def Transpose(a): return Function("Transpose", (a,), MODULE)

def test_transpose_involutive_fires():
    A = Variable("A", MODULE)
    goal = Equality(Transpose(Transpose(A)), A)

    explorer = CoAIOperandicsExplorer(certified_mode=True)
    from prover.general_atp import GeneralATP
    from discovery.engine import KnowledgeBase
    kb = KnowledgeBase(axioms=explorer.axioms, theorems=explorer.lemmas, axiom_names=explorer.axiom_names)
    atp = GeneralATP()
    
    res = atp.prove(goal, kb)
    assert res.success, "Proof failed"
    assert "transpose_involutive" in res.applied_rules, "transpose_involutive rule did not fire"

if __name__ == "__main__":
    test_transpose_involutive_fires()
    print("test_transpose_involutive_fires passed")
