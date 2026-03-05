from __future__ import annotations
from typing import Any, Dict, Tuple

from core.logic import (
    Term, Formula, Sort,
    Function, Variable, Constant,
    Forall, Equality,
    MODULE, REAL, PROB, PRED, BOOL,
)

SORTS: Dict[str, Sort] = {
    "MODULE": MODULE,
    "REAL": REAL,
    "PROB": PROB,
    "PRED": PRED,
    "BOOL": BOOL,
}

from core.logic import OPERAD_SIGNATURES

ALLOWED_CONSTS = {"ID_M"}  # extend intentionally if needed


def parse_term(expr: Any, env: Dict[str, Term]) -> Term:
    if isinstance(expr, str):
        if expr in env:
            return env[expr]
        if expr in ALLOWED_CONSTS:
            if expr == "R_ZERO" or expr == "R_ONE":
                return Constant(expr, REAL)
            return Constant(expr, MODULE)
        raise ValueError(f"Unknown symbol (not a bound var or allowed const): {expr}")

    if not (isinstance(expr, list) and len(expr) >= 1):
        raise ValueError(f"Invalid term expression: {expr}")

    op = expr[0]
    if op not in OPERAD_SIGNATURES:
        raise ValueError(f"Unknown function symbol: {op}")

    args = tuple(parse_term(a, env) for a in expr[1:])
    return Function(op, args, OPERAD_SIGNATURES[op].result_sort)


def parse_formula(expr: Any, env: Dict[str, Term], var_sorts: Dict[str, str]) -> Formula:
    if not (isinstance(expr, list) and len(expr) >= 1):
        raise ValueError(f"Invalid formula expression: {expr}")

    op = expr[0]

    if op == "Forall":
        if len(expr) != 3:
            raise ValueError(f"Forall expects [Forall, var, body], got: {expr}")
        name = expr[1]
        if not isinstance(name, str):
            raise ValueError(f"Forall var must be a string, got: {name}")

        sort_name = var_sorts.get(name, "MODULE")
        if sort_name not in SORTS:
            raise ValueError(f"Unknown sort '{sort_name}' for var {name}")
        v = Variable(name, SORTS[sort_name])

        # shadowing is fine (nested Forall); store and restore
        old = env.get(name, None)
        env[name] = v
        body = parse_formula(expr[2], env, var_sorts)
        if old is None:
            del env[name]
        else:
            env[name] = old
        return Forall(v, body)

    if op == "Equality":
        if len(expr) != 3:
            raise ValueError(f"Equality expects [Equality, lhs, rhs], got: {expr}")
        lhs = parse_term(expr[1], env)
        rhs = parse_term(expr[2], env)
        return Equality(lhs, rhs)

    raise ValueError(f"Unknown formula operator: {op}")
