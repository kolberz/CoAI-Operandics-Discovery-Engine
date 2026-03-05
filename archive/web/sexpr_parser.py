from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Union

from core.logic import (
    Variable, Constant, Function,
    Atom, Equality, LessEq, Not, And, Or, Implies, Forall, Exists,
    MODULE, REAL, PROB, BOOL, PRED
)

class ParseError(Exception): pass

Token = str
Sexp = Union[str, List["Sexp"]]

def tokenize(s: str) -> List[Token]:
    s = s.replace("(", " ( ").replace(")", " ) ")
    # strip comments starting with ;
    lines = []
    for line in s.splitlines():
        if ";" in line:
            line = line.split(";", 1)[0]
        lines.append(line)
    s = "\n".join(lines)
    return [t for t in s.split() if t]

def parse_sexp(tokens: List[Token]) -> Tuple[Sexp, List[Token]]:
    if not tokens:
        raise ParseError("unexpected EOF")
    t = tokens.pop(0)
    if t == "(":
        out = []
        while tokens and tokens[0] != ")":
            node, tokens = parse_sexp(tokens)
            out.append(node)
        if not tokens:
            raise ParseError("missing ')'")
        tokens.pop(0)  # )
        return out, tokens
    if t == ")":
        raise ParseError("unexpected ')'")
    return t, tokens

def parse_many(s: str) -> List[Sexp]:
    toks = tokenize(s)
    sexps = []
    while toks:
        node, toks = parse_sexp(toks)
        sexps.append(node)
    return sexps

def sort_from_str(x: str):
    m = {
        "MODULE": MODULE,
        "REAL": REAL,
        "PROB": PROB,
        "BOOL": BOOL,
        "PRED": PRED,
    }
    if x not in m:
        raise ParseError(f"Unknown sort: {x}")
    return m[x]

@dataclass
class Env:
    vars: dict

def term(node: Sexp, env: Env):
    if isinstance(node, str):
        # variable if bound, else constant
        if node in env.vars:
            return env.vars[node]
        return Constant(node)

    # list: (f arg1 arg2 ...)
    if not node:
        raise ParseError("empty term list")
    head = node[0]
    if not isinstance(head, str):
        raise ParseError("function head must be symbol")
    args = tuple(term(x, env) for x in node[1:])
    return Function(symbol=head, args=args)

def formula(node: Sexp, env: Env):
    if isinstance(node, str):
        # atoms as predicates not supported as bare symbol; treat as Atom(pred,())
        return Atom(predicate=node, args=())

    if not node:
        raise ParseError("empty formula list")

    head = node[0]
    if head == "not":
        return Not(formula=formula(node[1], env))
    if head == "and":
        # binary in your AST
        return And(left=formula(node[1], env), right=formula(node[2], env))
    if head == "or":
        return Or(left=formula(node[1], env), right=formula(node[2], env))
    if head == "implies":
        return Implies(antecedent=formula(node[1], env), consequent=formula(node[2], env))
    if head == "=":
        return Equality(left=term(node[1], env), right=term(node[2], env))
    if head == "<=":
        return LessEq(left=term(node[1], env), right=term(node[2], env))
    if head == "forall":
        # (forall (X SORT) BODY)
        binder = node[1]
        if not (isinstance(binder, list) and len(binder) == 2 and isinstance(binder[0], str) and isinstance(binder[1], str)):
            raise ParseError("forall binder must be (NAME SORT)")
        name, sort_s = binder
        v = Variable(name=name, sort=sort_from_str(sort_s))
        env2 = Env(vars=dict(env.vars))
        env2.vars[name] = v
        return Forall(variable=v, body=formula(node[2], env2))
    if head == "exists":
        binder = node[1]
        name, sort_s = binder
        v = Variable(name=name, sort=sort_from_str(sort_s))
        env2 = Env(vars=dict(env.vars))
        env2.vars[name] = v
        return Exists(variable=v, body=formula(node[2], env2))

    # fallback: treat as Atom(predicate, args)
    if not isinstance(head, str):
        raise ParseError("atom head must be symbol")
    args = tuple(term(x, env) for x in node[1:])
    return Atom(predicate=head, args=args)

def parse_axioms_sexpr(text: str):
    sexps = parse_many(text)
    axioms = []
    names = []
    for i, sx in enumerate(sexps):
        axioms.append(formula(sx, Env(vars={})))
        names.append(f"axiom_{i}")
    return axioms, names
