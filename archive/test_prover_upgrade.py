import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from core.logic import *
from prover.general_atp import GeneralProver

def test_prover():
    prover = GeneralProver()
    # Simple transitivity ax: f(X) = Y and g(Y) = Z -> h(X) = Z
    # We will just test A=B, B=C |- A=C
    a = Constant("A", MODULE)
    b = Constant("B", MODULE)
    c = Constant("C", MODULE)
    
    prover.add_axiom(Equality(a, b))
    prover.add_axiom(Equality(b, c))
    
    goal = Equality(a, c)
    print("Starting proof...")
    res = prover.prove(goal, max_steps=100, timeout_seconds=5.0)
    print(f"Success: {res.success}")
    for step in res.proof_trace:
        print(step)

if __name__ == "__main__":
    test_prover()
