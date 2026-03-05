from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import hashlib
from pathlib import Path

from discovery.engine import CoAIOperandicsExplorer
from core.logic import Function, Variable, Equality, MODULE

# -----------------------------
# Helpers: attention symbols
# -----------------------------
def Compose(a, b): return Function("Compose", (a, b), MODULE)
def Transpose(a): return Function("Transpose", (a,), MODULE)
def phi(a): return Function("phi", (a,), MODULE)
def Attn(q, k, v): return Function("Attn", (q, k, v), MODULE)

def bundle_hash(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()[:16]

def find_general_atp(explorer: CoAIOperandicsExplorer):
    """
    Tries to locate the GeneralATP instance from the explorer object.
    Adjust if your field names differ. This is defensive so the demo
    doesn’t depend on one attribute name.
    """
    for name in ["atp", "prover", "general_atp", "GeneralATP", "ATP", "_verifier", "verifier", "saturator"]:
        if hasattr(explorer, name):
            obj = getattr(explorer, name)
            if hasattr(obj, "prove"):
                return obj
            # Special case for saturator
            if name == "saturator" and hasattr(obj, "prover"):
                return obj.prover
    # Common nesting patterns
    for name in ["engine", "session"]:
        if hasattr(explorer, name):
            obj = getattr(explorer, name)
            for sub in ["atp", "prover", "general_atp", "verifier", "_verifier"]:
                if hasattr(obj, sub):
                    return getattr(obj, sub)
    raise RuntimeError(f"Could not find GeneralATP instance on explorer; paste explorer.__dict__ keys: {explorer.__dict__.keys()}")

def main():
    verified = Path("discovery/axioms/attention_axioms.verified.json")
    assert verified.exists(), f"Missing verified bundle: {verified}"

    print(f"[OK] Found verified bundle: {verified}")
    print(f"[INFO] Bundle sha256[:16] = {bundle_hash(verified)}")

    # Optional: print rule IDs present (sanity)
    bundle = json.loads(verified.read_text(encoding="utf-8"))
    rule_ids = [r["id"] for r in bundle.get("rules", [])]
    print(f"[INFO] Bundle rules: {rule_ids}")
    assert "linear_attention_associativity" in rule_ids, "Expected rule id not present in verified bundle."

    # Build the goal formula
    Q = Variable("Q", MODULE)
    K = Variable("K", MODULE)
    V = Variable("V", MODULE)

    lhs = Compose(phi(Q), Compose(Transpose(phi(K)), V))
    rhs = Attn(Q, K, V)
    goal = Equality(lhs, rhs)

    print("[INFO] Goal:", goal)

    # Initialize explorer (this should cause engine KB init and rule loading)
    explorer = CoAIOperandicsExplorer()

    # Locate prover and prove goal
    from prover.general_atp import GeneralATP
    atp = GeneralATP()

    # Call the prover.
    from discovery.engine import KnowledgeBase
    kb = KnowledgeBase(axioms=explorer.axioms, theorems=explorer.lemmas, axiom_names=explorer.axiom_names)
    
    try:
        result = atp.prove(goal, kb)
    except TypeError:
        # Fallback signature guesses:
        result = atp.prove(goal, kb, max_steps=100, timeout=10.0)

    print("\n=== ProofResult ===")
    print("success:", result.success)
    print("time_taken:", getattr(result, "time_taken", None))
    print("nodes_explored:", getattr(result, "nodes_explored", None))
    print("applied_rules:", result.applied_rules)
    for line in result.proof_trace:
        print(" ", line)

    assert result.success, "Proof failed: expected to succeed via certified rewrite."
    assert "linear_attention_associativity" in result.applied_rules, \
        "Certified rule was not referenced in the applied_rules trace."

    print("\n[OK] Demo succeeded: certified attention rule applied and traced.")

if __name__ == "__main__":
    main()
