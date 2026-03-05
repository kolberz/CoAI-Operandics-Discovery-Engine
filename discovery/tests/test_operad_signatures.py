import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from core.logic import (
    MODULE, REAL, PROB,
    Variable, Constant, Function, Term
)

def test_correctly_typed_signatures():
    M = Variable("M", MODULE)
    P = Variable("P", PROB)
    R = Variable("R", REAL)

    # Compose(MODULE,MODULE)->MODULE
    c = Function("Compose", (M, M), MODULE)
    assert c.sort == MODULE
    assert c.symbol == "Compose"

    # Transpose(MODULE)->MODULE
    t = Function("Transpose", (M,), MODULE)
    assert t.sort == MODULE

    # prob_weight(PROB, REAL)->REAL
    pw = Function("prob_weight", (P, R), REAL)
    assert pw.sort == REAL

    # variadic add(REAL, REAL, ...)->REAL
    a = Function("add", (R, R, R), REAL)
    assert a.sort == REAL


def test_incorrectly_typed_signatures_fail():
    M = Variable("M", MODULE)
    R = Variable("R", REAL)

    with pytest.raises(ValueError, match="Arg sort mismatch for 'Compose': got Real, expected Module"):
        Function("Compose", (R, M), MODULE)

    with pytest.raises(ValueError, match="Arg sort mismatch for 'Transpose': got Real, expected Module"):
        Function("Transpose", (R,), MODULE)

    with pytest.raises(ValueError, match="Result sort mismatch for 'Compose': got Real, expected Module"):
        Function("Compose", (M, M), REAL)

def test_unknown_symbol_fails():
    M = Variable("M", MODULE)
    with pytest.raises(ValueError, match="Unknown function symbol 'UNKNOWN'"):
        Function("UNKNOWN", (M,), MODULE)

def test_untyped_leaf_fails():
    # If a class inherits Term but has no .sort
    class BadLeaf(Term):
        def variables(self): return set()
        def substitute(self, m): return self
        def depth(self): return 0
        def size(self): return 1
        def functions(self): return set()
    
    bad = BadLeaf()
    M = Variable("M", MODULE)
    
    with pytest.raises(ValueError, match=r"Untyped leaf term.*has no \.sort"):
        Function("Compose", (bad, M), MODULE)
