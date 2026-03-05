"""
core/unification.py

Robinson's unification algorithm with occurs check.
"""

from core.logic import *
from typing import Optional


class UnificationFailure(Exception):
    pass


def occurs_check(var: Variable, term: Term) -> bool:
    """Check if var occurs in term (prevents infinite types)."""
    if isinstance(term, Variable):
        return var == term
    elif isinstance(term, Constant):
        return False
    elif isinstance(term, Function):
        return any(occurs_check(var, arg) for arg in term.args)
    return False


def apply_substitution(term: Term, subst: Dict[Variable, Term]) -> Term:
    """Apply substitution to a term, recursively."""
    if isinstance(term, Variable):
        if term in subst:
            return apply_substitution(subst[term], subst)
        return term
    elif isinstance(term, Constant):
        return term
    elif isinstance(term, Function):
        new_args = tuple(apply_substitution(arg, subst) for arg in term.args)
        return Function(term.symbol, new_args, term.sort)
    return term


def apply_substitution_to_formula(formula: Formula, subst: Dict[Variable, Term]) -> Formula:
    """Apply substitution to all terms in a formula."""
    if isinstance(formula, Atom):
        new_args = tuple(apply_substitution(arg, subst) for arg in formula.args)
        return Atom(formula.predicate, new_args)
    elif isinstance(formula, Equality):
        return Equality(
            apply_substitution(formula.left, subst),
            apply_substitution(formula.right, subst)
        )
    elif isinstance(formula, LessEq):
        return LessEq(
            apply_substitution(formula.left, subst),
            apply_substitution(formula.right, subst)
        )
    elif isinstance(formula, Not):
        return Not(apply_substitution_to_formula(formula.formula, subst))
    elif isinstance(formula, And):
        return And(
            apply_substitution_to_formula(formula.left, subst),
            apply_substitution_to_formula(formula.right, subst)
        )
    elif isinstance(formula, Or):
        return Or(
            apply_substitution_to_formula(formula.left, subst),
            apply_substitution_to_formula(formula.right, subst)
        )
    elif isinstance(formula, Implies):
        return Implies(
            apply_substitution_to_formula(formula.antecedent, subst),
            apply_substitution_to_formula(formula.consequent, subst)
        )
    elif isinstance(formula, Forall):
        if formula.variable in subst:
            new_subst = {k: v for k, v in subst.items() if k != formula.variable}
        else:
            new_subst = subst
        return Forall(formula.variable, apply_substitution_to_formula(formula.body, new_subst))
    elif isinstance(formula, Exists):
        if formula.variable in subst:
            new_subst = {k: v for k, v in subst.items() if k != formula.variable}
        else:
            new_subst = subst
        return Exists(formula.variable, apply_substitution_to_formula(formula.body, new_subst))
    return formula


def apply_substitution_to_literal(lit: Literal, subst: Dict[Variable, Term]) -> Literal:
    """Apply substitution to a literal."""
    return Literal(apply_substitution_to_formula(lit.atom, subst), lit.positive)


def apply_substitution_to_clause(clause: Clause, subst: Dict[Variable, Term]) -> Clause:
    """Apply substitution to all literals in a clause."""
    return Clause(
        frozenset(apply_substitution_to_literal(lit, subst) for lit in clause.literals),
        clause.source
    )


def compose_substitutions(s1: Dict[Variable, Term], s2: Dict[Variable, Term]) -> Dict[Variable, Term]:
    """Compose two substitutions: first apply s1, then s2."""
    result = {}
    for var, term in s1.items():
        result[var] = apply_substitution(term, s2)
    for var, term in s2.items():
        if var not in result:
            result[var] = term
    return {k: v for k, v in result.items() if not (isinstance(v, Variable) and v == k)}


def unify_terms(t1: Term, t2: Term, subst: Optional[Dict[Variable, Term]] = None) -> Optional[Dict[Variable, Term]]:
    """
    Unify two terms under existing substitution.
    Returns the most general unifier (MGU) or None if unification fails.
    """
    if subst is None:
        subst = {}
    
    t1 = apply_substitution(t1, subst)
    t2 = apply_substitution(t2, subst)
    
    if t1 == t2:
        return subst

    if t1.sort != t2.sort:
        return None
    
    if isinstance(t1, Variable):
        if occurs_check(t1, t2):
            return None
        return compose_substitutions(subst, {t1: t2})
    
    if isinstance(t2, Variable):
        if occurs_check(t2, t1):
            return None
        return compose_substitutions(subst, {t2: t1})
    
    if isinstance(t1, Constant) and isinstance(t2, Constant):
        if t1.name == t2.name:
            return subst
        return None
    
    if isinstance(t1, Function) and isinstance(t2, Function):
        if t1.symbol != t2.symbol or len(t1.args) != len(t2.args):
            return None
        current_subst = subst
        for a1, a2 in zip(t1.args, t2.args):
            current_subst = unify_terms(a1, a2, current_subst)
            if current_subst is None:
                return None
        return current_subst
    
    return None


def unify_atoms(a1: Formula, a2: Formula, subst: Optional[Dict[Variable, Term]] = None) -> Optional[Dict[Variable, Term]]:
    """Unify two atomic formulas (Atom, Equality, or LessEq)."""
    if subst is None:
        subst = {}
    
    if isinstance(a1, Atom) and isinstance(a2, Atom):
        if a1.predicate != a2.predicate or len(a1.args) != len(a2.args):
            return None
        current = subst
        for t1, t2 in zip(a1.args, a2.args):
            current = unify_terms(t1, t2, current)
            if current is None:
                return None
        return current
    
    if isinstance(a1, Equality) and isinstance(a2, Equality):
        result = unify_terms(a1.left, a2.left, subst)
        if result is not None:
            result = unify_terms(a1.right, a2.right, result)
            if result is not None:
                return result
        result = unify_terms(a1.left, a2.right, subst)
        if result is not None:
            result = unify_terms(a1.right, a2.left, result)
            return result
        return None
    
    if isinstance(a1, LessEq) and isinstance(a2, LessEq):
        result = unify_terms(a1.left, a2.left, subst)
        if result is not None:
            return unify_terms(a1.right, a2.right, result)
        return None
    
    return None


def rename_variables(clause: Clause, suffix: str) -> Clause:
    """Rename all variables in a clause to avoid capture."""
    var_map = {}
    for var in clause.variables():
        new_var = Variable(f"{var.name}_{suffix}", var.sort)
        var_map[var] = new_var
    return apply_substitution_to_clause(clause, var_map)
