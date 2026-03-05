"""
build290_architect_intelligence.py

Implements a domain-specific theorem prover for Process Algebra / Systems Architecture.
Integrates directly with the `ForwardChainingSaturator` from `build270_merged_spec.py`.
"""

from __future__ import annotations
import sys
import itertools
from typing import Optional, Iterator, Iterable
from dataclasses import dataclass

try:
    from build270_merged_spec import (
        ClauseOps, ForwardChainingSaturator, SaturationLimits,
        InterestingnessScorer, InterestingnessContext, InterestingnessWeights,
        FormulaIntrospection, DiscoveredTheorem
    )
except ImportError:
    print("FATAL: build270_merged_spec.py not found. Ensure it is in the same directory.")
    sys.exit(1)

# =============================================================================
# SECTION 1 — Term & Equation Representation
# =============================================================================

@dataclass(frozen=True, order=True)
class Var:
    name: str
    def __str__(self): return self.name

@dataclass(frozen=True, order=True)
class Func:
    symbol: str
    args: tuple['Term', ...] = ()
    def __str__(self):
        if not self.args: return self.symbol
        return f"{self.symbol}({', '.join(str(a) for a in self.args)})"

Term = Var | Func

@dataclass(frozen=True, order=True)
class Equation:
    lhs: Term
    rhs: Term
    def __str__(self): return f"{self.lhs} = {self.rhs}"

# =============================================================================
# SECTION 2 — Subterm Rewriting & Paramodulation Mechanics
# =============================================================================

def is_pat_var(v: Var) -> bool:
    return v.name.startswith("_")

def match_term(pat: Term, target: Term, subst: dict[Var, Term]) -> bool:
    if isinstance(pat, Var):
        if is_pat_var(pat):
            if pat in subst: return subst[pat] == target
            subst[pat] = target
            return True
        return pat == target
    
    if isinstance(pat, Func) and isinstance(target, Func):
        if pat.symbol != target.symbol or len(pat.args) != len(target.args):
            return False
        for pa, ta in zip(pat.args, target.args):
            if not match_term(pa, ta, subst): return False
        return True
    return False

def apply_subst(t: Term, subst: dict[Var, Term]) -> Term:
    if isinstance(t, Var): return subst.get(t, t)
    return Func(t.symbol, tuple(apply_subst(a, subst) for a in t.args))

def term_size(t: Term) -> int:
    if isinstance(t, Var): return 1
    return 1 + sum(term_size(a) for a in t.args)

def term_key(t: Term) -> tuple[int, str]:
    return (term_size(t), str(t))

@dataclass(frozen=True)
class RewriteRule:
    lhs: Term
    rhs: Term

def orient(eq: Equation) -> Optional[RewriteRule]:
    lk, rk = term_key(eq.lhs), term_key(eq.rhs)
    if lk > rk: return RewriteRule(eq.lhs, eq.rhs)
    if rk > lk: return RewriteRule(eq.rhs, eq.lhs)
    return None

def rewrite_anywhere_one_step(target: Term, rule: RewriteRule) -> Iterator[Term]:
    subst = {}
    if match_term(rule.lhs, target, subst):
        out = apply_subst(rule.rhs, subst)
        if term_key(out) < term_key(target):
            yield out
            
    if isinstance(target, Func):
        for i, arg in enumerate(target.args):
            for new_arg in rewrite_anywhere_one_step(arg, rule):
                new_args = list(target.args)
                new_args[i] = new_arg
                yield Func(target.symbol, tuple(new_args))

# =============================================================================
# SECTION 3 — Canonicalization & Fixed-Point Simplification
# =============================================================================

COMMUTATIVE = {"Plus", "Max", "Min"}

def sort_args(t: Term) -> Term:
    if isinstance(t, Var): return t
    new_args = tuple(sort_args(a) for a in t.args)
    if t.symbol in COMMUTATIVE:
        new_args = tuple(sorted(new_args, key=term_key))
    return Func(t.symbol, new_args)

_x, _y = Var("_x"), Var("_y")

SIMP_RULES = [
    RewriteRule(Func("Cost", (Func("ID", ()),)), Func("Zero", ())),
    RewriteRule(Func("Risk", (Func("ID", ()),)), Func("Zero", ())),
    RewriteRule(Func("Plus", (_x, Func("Zero", ()))), _x),
    RewriteRule(Func("Plus", (Func("Zero", ()), _x)), _x),
    RewriteRule(Func("Plus", (Func("Zero", ()), Func("Zero", ()))), Func("Zero", ())),
    RewriteRule(Func("Max", (_x, _x)), _x),
    RewriteRule(Func("Min", (_x, _x)), _x),
    RewriteRule(Func("Max", (_x, Func("Zero", ()))), _x),
    RewriteRule(Func("Max", (Func("Zero", ()), _x)), _x),
    RewriteRule(Func("Min", (_x, Func("Zero", ()))), Func("Zero", ())),
    RewriteRule(Func("Min", (Func("Zero", ()), _x)), Func("Zero", ())),
]

def simplify_term(t: Term) -> Term:
    if isinstance(t, Var): return t
    new_args = tuple(simplify_term(a) for a in t.args)
    t = Func(t.symbol, new_args)
    t = sort_args(t)
    
    for rule in SIMP_RULES:
        subst = {}
        if match_term(rule.lhs, t, subst):
            return simplify_term(apply_subst(rule.rhs, subst))
    return t

def canonicalize_eq(eq: Equation) -> Equation:
    """FIX 1: Puts the heavier term on the LHS for is_reduction matching."""
    l = simplify_term(eq.lhs)
    r = simplify_term(eq.rhs)
    if term_key(l) < term_key(r):
        return Equation(r, l)
    return Equation(l, r)

# =============================================================================
# SECTION 4 — ArchitectOps Protocol Implementation
# =============================================================================

class ArchitectOps(ClauseOps[Equation, Equation]):
    def canonicalize(self, c: Equation) -> Equation:
        return canonicalize_eq(c)
        
    def weight(self, c: Equation) -> int:
        return term_size(c.lhs) + term_size(c.rhs)
        
    def redundant(self, c: Equation, *, active: set[Equation]) -> bool:
        if c.lhs == c.rhs: return True
        return c in active
        
    def admissible(self, c: Equation, *, depth: int) -> bool:
        if c.lhs == c.rhs: return False
        if term_size(c.lhs) + term_size(c.rhs) > 40: return False  # Bumped ceiling
        return True
        
    def resolve(self, given: Equation, other: Equation) -> Iterable[Equation]:
        """FIX 2: Deduplicated complete-for-{a,b} paramodulation."""
        rg = orient(given)
        ro = orient(other)
        
        def emit(rule: RewriteRule, eq: Equation) -> Iterator[Equation]:
            # Throughput guard: cap at 10 rewrites per side to limit fan-out
            n = 0
            for new_lhs in rewrite_anywhere_one_step(eq.lhs, rule):
                yield Equation(new_lhs, eq.rhs)
                n += 1
                if n >= 10: break
            n = 0
            for new_rhs in rewrite_anywhere_one_step(eq.rhs, rule):
                yield Equation(eq.lhs, new_rhs)
                n += 1
                if n >= 10: break
                
        if rg is not None:
            yield from emit(rg, other)  # given rewrites other
        if ro is not None:
            yield from emit(ro, given)  # other rewrites given
                
    def to_formula(self, c: Equation) -> Equation:
        return c

# =============================================================================
# SECTION 5 — Interestingness Introspection Hooks
# =============================================================================

class ArchitectIntrospection(FormulaIntrospection[Equation]):
    def symbols(self, f: Equation) -> set[str]:
        def get_syms(t: Term) -> set[str]:
            if isinstance(t, Func):
                s = {t.symbol}
                for a in t.args: s |= get_syms(a)
                return s
            return set()
        return get_syms(f.lhs) | get_syms(f.rhs)
        
    def complexity(self, f: Equation) -> int:
        return term_size(f.lhs) + term_size(f.rhs)
        
    def is_reduction(self, f: Equation) -> bool:
        return term_size(f.lhs) > term_size(f.rhs) + 1
        
    def is_symmetric(self, f: Equation) -> bool: return False
    def is_associative(self, f: Equation) -> bool: return False
    def is_trivial_identity(self, f: Equation) -> bool: return f.lhs == f.rhs

# =============================================================================
# SECTION 6 — Axiom Generation & Main Loop
# =============================================================================

def make_architect_axioms() -> list[Equation]:
    terms = [Func("ID"), Func("A"), Func("B"), Func("C")]
    axioms = []
    
    for t1 in terms:
        for t2 in terms:
            axioms.append(Equation(Func("Cost", (Func("Seq", (t1, t2)),)), 
                                   Func("Plus", (Func("Cost", (t1,)), Func("Cost", (t2,))))))
            axioms.append(Equation(Func("Cost", (Func("Par", (t1, t2)),)), 
                                   Func("Max", (Func("Cost", (t1,)), Func("Cost", (t2,))))))
            axioms.append(Equation(Func("Risk", (Func("Seq", (t1, t2)),)), 
                                   Func("Plus", (Func("Risk", (t1,)), Func("Risk", (t2,))))))
            axioms.append(Equation(Func("Risk", (Func("Par", (t1, t2)),)), 
                                   Func("Min", (Func("Risk", (t1,)), Func("Risk", (t2,))))))
    
    # Inject depth-2 nested configurations to trigger deep paramodulation chains.
    # Avoid nests containing ID — those collapse to simpler forms via simplifier.
    _A, _B, _C = Func("A"), Func("B"), Func("C")
    
    nested_terms = [
        # Seq-Par nesting (no ID — these survive canonicalization)
        Func("Seq", (Func("Par", (_A, _B)), _C)),                       # Seq(Par(A,B), C)
        Func("Par", (Func("Seq", (_A, _B)), _C)),                       # Par(Seq(A,B), C)
        Func("Seq", (_A, Func("Par", (_B, _C)))),                       # Seq(A, Par(B,C))
        Func("Par", (_A, Func("Seq", (_B, _C)))),                       # Par(A, Seq(B,C))
        # Double nesting (all non-ID)
        Func("Seq", (Func("Seq", (_A, _B)), Func("Seq", (_B, _C)))),    # Seq(Seq(A,B), Seq(B,C))
        Func("Par", (Func("Par", (_A, _B)), Func("Par", (_B, _C)))),    # Par(Par(A,B), Par(B,C))
        # Cross nesting
        Func("Seq", (Func("Par", (_A, _B)), Func("Seq", (_C, _A)))),    # Seq(Par(A,B), Seq(C,A))
        Func("Par", (Func("Seq", (_A, _C)), Func("Par", (_B, _A)))),    # Par(Seq(A,C), Par(B,A))
        # Triple depth
        Func("Seq", (Func("Par", (Func("Seq", (_A, _B)), _C)), _A)),    # Seq(Par(Seq(A,B),C), A)
        Func("Par", (Func("Seq", (Func("Par", (_A, _C)), _B)), _C)),    # Par(Seq(Par(A,C),B), C)
    ]
    
    # Directly generate the distribution axioms (no placeholders)
    for nt in nested_terms:
        x, y = nt.args
        if nt.symbol == "Seq":
            axioms.append(Equation(
                Func("Cost", (nt,)), Func("Plus", (Func("Cost", (x,)), Func("Cost", (y,))))))
            axioms.append(Equation(
                Func("Risk", (nt,)), Func("Plus", (Func("Risk", (x,)), Func("Risk", (y,))))))
        elif nt.symbol == "Par":
            axioms.append(Equation(
                Func("Cost", (nt,)), Func("Max", (Func("Cost", (x,)), Func("Cost", (y,))))))
            axioms.append(Equation(
                Func("Risk", (nt,)), Func("Min", (Func("Risk", (x,)), Func("Risk", (y,))))))
    
    return axioms

if __name__ == "__main__":
    ops = ArchitectOps()
    hooks = ArchitectIntrospection()
    
    # FIX 3a: Custom context for our domain alphabet
    ctx = InterestingnessContext(
        compositional_symbols=frozenset({"Seq", "Par", "Cost", "Risk", "Plus", "Max", "Min", "ID", "Zero"})
    )
    
    scorer = InterestingnessScorer(hooks, min_interestingness=0.45)
    
    sat = ForwardChainingSaturator(
        ops=ops,
        scorer=scorer,
        limits=SaturationLimits(
            max_depth=15,
            max_generated=50000,
            max_given_steps=5000,
        )
    )
    sat.score_ctx = ctx  # Apply custom context
    
    print("Loading Architect Axioms...")
    sat.push_axioms(make_architect_axioms())
    
    print("Running Architect Intelligence Saturator...")
    for _ in sat.run():
        pass
        
    print(f"\nStats: given={sat.stats.given_steps}, generated={sat.stats.generated}, active={len(sat.active)}")
    
    # FIX 3b: Score and surface the Active set directly
    print("\n--- TOP ACTIVE CLAUSES BY INTERESTINGNESS ---")
    ranked = [(scorer.score(c, ctx), str(c), c) for c in sat.active]
    ranked.sort(reverse=True)  # sorts by score, then str(c) for determinism

    count = 0
    for s, _, c in ranked:
        if s >= scorer.min_interestingness:
            print(f"[{s:.3f}] {c}")
            count += 1
            if count >= 25: break
