from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pathlib import Path
from discovery.engine import CoAIOperandicsExplorer, KnowledgeBase
from prover.general_atp import GeneralATP
from core.logic import Function, Variable, Equality, MODULE

def Compose(a, b): return Function("Compose", (a, b), MODULE)
def Transpose(a): return Function("Transpose", (a,), MODULE)
def phi(a): return Function("phi", (a,), MODULE)
def Attn(q, k, v): return Function("Attn", (q, k, v), MODULE)

def test_certified_attention_rule_fires():
    verified = Path(__file__).resolve().parents[1] / "axioms" / "attention_axioms.verified.json"
    assert verified.exists(), f"Missing verified bundle: {verified}, run add_attention_axioms.py first."
    
    Q = Variable("Q", MODULE)
    K = Variable("K", MODULE)
    V = Variable("V", MODULE)
    lhs = Compose(phi(Q), Compose(Transpose(phi(K)), V))
    rhs = Attn(Q, K, V)
    goal = Equality(lhs, rhs)
    
    explorer = CoAIOperandicsExplorer()
    atp = GeneralATP()
    kb = KnowledgeBase(axioms=explorer.axioms, theorems=explorer.lemmas, axiom_names=explorer.axiom_names)
    
    result = atp.prove(goal, kb)
    
    assert result.success, "Proof failed"
    assert "linear_attention_associativity" in result.applied_rules, "Certified rule did not fire"

if __name__ == "__main__":
    test_certified_attention_rule_fires()
    print("Regression test passed.")
