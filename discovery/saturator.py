"""
discovery/saturator.py

Build 2.7.0 Hardened Forward-Chaining Saturation Engine.
Uses a Given Clause Loop with deterministic Active/Passive sets.
Integrates RiskEGraph normalization into the canonicalization choke-point.
"""

from __future__ import annotations
import heapq
import itertools
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Hashable,
    Iterable,
    Iterator,
    Protocol,
    TypeVar,
    Generic,
    List,
    Set,
    Dict,
    Tuple,
    Optional,
)

import core.logic as cl
from core.unification import *
from prover.general_atp import to_cnf, resolve_clauses, paramodulate, subsumes, is_tautology
from discovery.normalization import (
    RiskEGraph, logic_to_egraph_term, egraph_term_to_logic, ERewrite, saturate_with_rewrites
)
from prover.heuristics import SemanticHeuristic

# =============================================================================
# SECTION 1 — Protocols and Type Variables
# =============================================================================

ClauseT = TypeVar("ClauseT", bound=Hashable)
FormulaT = TypeVar("FormulaT")

class ClauseOps(Protocol[ClauseT, FormulaT]):
    """Pluggable operations for the saturator."""
    def canonicalize(self, c: ClauseT) -> ClauseT: ...
    def weight(self, c: ClauseT) -> int: ...
    def resolve(self, a: ClauseT, b: ClauseT) -> Iterable[ClauseT]: ...
    def redundant(self, c: ClauseT, *, active: set[ClauseT]) -> bool: ...
    def admissible(self, c: ClauseT, *, depth: int) -> bool: ...
    def to_formula(self, c: ClauseT) -> FormulaT: ...

# =============================================================================
# SECTION 2 — Operandics Specific Adapter
# =============================================================================

@dataclass(slots=True)
class OperandicsClauseOps(ClauseOps[cl.Clause, cl.Formula]):
    """
    Adapter for CoAI Operandics logic (Build 2.9.0 Architect).
    Integrates demodulation and paramodulation-lite for refactoring.
    """
    egraph: RiskEGraph
    heuristic: SemanticHeuristic = field(default_factory=SemanticHeuristic)
    max_depth: int = 25
    max_rewrites_per_step: int = 6
    demodulators: List[ERewrite] = field(default_factory=list)
    mode: str = "full"  # "full", "topological", "algebraic"

    def canonicalize(self, c: cl.Clause) -> cl.Clause:
        """Deeply simplify a clause using demodulation and e-graph roots."""
        from discovery.normalization import (
            normalize_innermost, logic_to_egraph_term, egraph_term_to_logic
        )
        
        new_lits = []
        for lit in c.literals:
            atom = lit.atom
            if isinstance(atom, (cl.Equality, cl.LessEq)):
                L = self._normalize_term_architect(atom.left)
                R = self._normalize_term_architect(atom.right)
                # Build 2.9.0: Orient Equality so LHS is "heavier"
                if str(L) < str(R): L, R = R, L
                new_atom = type(atom)(L, R)
            elif isinstance(atom, cl.Atom):
                new_args = tuple(self._normalize_term_architect(a) for a in atom.args)
                new_atom = cl.Atom(atom.predicate, new_args)
            else:
                new_atom = atom
            new_lits.append(cl.Literal(new_atom, lit.positive))
        return cl.Clause(frozenset(new_lits), source=c.source)

    def _normalize_term_architect(self, term: cl.Term) -> cl.Term:
        """
        Build 2.9.0: deep normalization using:
        1. Commutative sorting
        2. Innermost demodulation (directed simplification)
        3. E-Graph root lookup (congruence)
        """
        from discovery.normalization import (
            normalize_innermost, logic_to_egraph_term, egraph_term_to_logic
        )
        # 1. Commutative sorting
        term = self._sort_commutative(term)
        
        # 2. Innermost demodulation
        et = logic_to_egraph_term(term)
        net = normalize_innermost(et, self.demodulators)
        
        # 3. E-Graph root
        root_id = self.egraph.add(net)
        final_et = self.egraph._rep[self.egraph.find(root_id)]
        
        return egraph_term_to_logic(final_et)

    def _sort_commutative(self, term: cl.Term) -> cl.Term:
        """Sort arguments for commutative symbols (Plus, Max, Min)."""
        if isinstance(term, cl.Function):
            new_args = tuple(self._sort_commutative(a) for a in term.args)
            if term.symbol in {"Plus", "Max", "Min", "Par", "Choice"}:
                # Sort args by string representation for canonical order
                new_args = tuple(sorted(new_args, key=str))
            return cl.Function(term.symbol, new_args, term.sort)
        return term

    def _normalize_term(self, term: cl.Term) -> cl.Term:
        try:
            et = logic_to_egraph_term(term)
            root_id = self.egraph.add(et)
            root_term = self.egraph._rep[self.egraph.find(root_id)]
            return egraph_term_to_logic(root_term)
        except Exception:
            return term

    def weight(self, c: cl.Clause) -> int:
        return int(-self.heuristic.score_clause(c) * 1000)

    def resolve(self, a: cl.Clause, b: cl.Clause) -> Iterable[cl.Clause]:
        """Build 2.9.0: Paramodulation-lite (Subterm Rewriting)."""
        step_id = f"res_{hash(a)}_{hash(b)}"
        
        # 1. Standard Resolution & Paramodulation (Root-based)
        try:
            res = resolve_clauses(a, b, step_id)
            for r in res: yield r
        except Exception: pass

        # 2. Architect-lite: Use 'a' as a rewrite rule on 'b' and vice-versa
        # This allows deep subterm optimization
        for (r1, r2) in [(a, b), (b, a)]:
            if r1.is_unit():
                lit = next(iter(r1.literals))
                if lit.positive and isinstance(lit.atom, cl.Equality):
                    # Attempt subterm rewriting (directed)
                    for new_clause in self._paramod_subterms(lit.atom, r2):
                        yield new_clause

    def _paramod_subterms(self, rule_eq: cl.Equality, target_clause: cl.Clause) -> Iterable[cl.Clause]:
        """Perform subterm paramodulation using rule_eq on target_clause."""
        # Simple implementation: DFS subterm replacement
        new_lits_list = list(target_clause.literals)
        for i, lit in enumerate(new_lits_list):
            atom = lit.atom
            if isinstance(atom, cl.Equality):
                # Try rewriting subterms of LHS and RHS
                for new_lhs in self._rewrite_all_subterms(atom.left, rule_eq):
                    new_lits = list(target_clause.literals)
                    new_lits[i] = cl.Literal(cl.Equality(new_lhs, atom.right), lit.positive)
                    yield cl.Clause(frozenset(new_lits), source=f"paramod_sub")
                for new_rhs in self._rewrite_all_subterms(atom.right, rule_eq):
                    new_lits = list(target_clause.literals)
                    new_lits[i] = cl.Literal(cl.Equality(atom.left, new_rhs), lit.positive)
                    yield cl.Clause(frozenset(new_lits), source=f"paramod_sub")

    def _rewrite_all_subterms(self, term: cl.Term, rule: cl.Equality) -> Iterable[cl.Term]:
        """Generate terms where ONE subterm is rewritten by rule."""
        from core.unification import unify_terms, apply_substitution
        
        # 1. Match at root (Robinson unification)
        subst = unify_terms(rule.left, term)
        if subst is not None:
            yield apply_substitution(rule.right, subst)
            
        # 2. Recurse
        if isinstance(term, cl.Function):
            for i, arg in enumerate(term.args):
                for new_arg in self._rewrite_all_subterms(arg, rule):
                    new_args = list(term.args)
                    new_args[i] = new_arg
                    yield cl.Function(term.symbol, tuple(new_args), term.sort)

    def redundant(self, c: cl.Clause, *, active: set[cl.Clause]) -> bool:
        if is_tautology(c): return True
        if c in active: return True
        return False

    def admissible(self, c: cl.Clause, *, depth: int) -> bool:
        if depth > self.max_depth: return False
        
        # O-FLOW: Topological Phase (Phase 1)
        if self.mode == "topological":
            # Only allow MODULE sorts. No REAL/PROB/PRED in atoms.
            for lit in c.literals:
                if not self._is_purely_topological(lit.atom):
                    return False
        
        # O-FLOW: Algebraic Phase (Phase 2)
        if self.mode == "algebraic":
            # Prevent topological changes: only allow terms that have the same MODULE structure
            # but different REAL/PROB/PRED leaves/args.
            # Simplified: Reject any clause that introduces a NEW MODULE-sort function symbol.
            # (Note: This is a heuristic for "filling constants").
            pass
        
        if c.is_empty(): return True
        return True

    def _is_purely_topological(self, atom: cl.Formula) -> bool:
        """Checks if an atom contains ONLY terms of MODULE sort."""
        if isinstance(atom, (cl.Equality, cl.LessEq)):
            return self._is_module_only(atom.left) and self._is_module_only(atom.right)
        if isinstance(atom, cl.Atom):
            return all(self._is_module_only(a) for a in atom.args)
        return True

    def _is_module_only(self, term: cl.Term) -> bool:
        """Deep check for MODULE sort and symbols."""
        if term.sort != cl.MODULE: return False
        if isinstance(term, cl.Function):
            return all(self._is_module_only(a) for a in term.args)
        return True

    def to_formula(self, c: cl.Clause) -> cl.Formula:
        if c.is_unit():
            lit = next(iter(c.literals))
            if lit.positive: return lit.atom
        return cl.Atom("Clause", (cl.Constant(str(c)),))

# =============================================================================
# SECTION 3 — Saturation Infrastructure
# =============================================================================

@dataclass(frozen=True, slots=True)
class ClauseProvenance:
    kind: str  # "axiom" | "resolvent"
    parents: tuple[int, int] | tuple[()] = ()
    rule: str = "resolve"
    depth: int = 0

@dataclass(frozen=True, slots=True)
class SaturationLimits:
    max_depth: int = 25
    max_active: int = 500
    max_passive: int = 5000
    max_generated: int = 10000
    max_given_steps: int = 1000

@dataclass(slots=True)
class SaturationStats:
    given_steps: int = 0
    generated: int = 0
    admitted_passive: int = 0
    admitted_active: int = 0
    redundant_skipped: int = 0

@dataclass(slots=True)
class SaturatorLoop(Generic[ClauseT, FormulaT]):
    """
    Forward chaining saturator using a given-clause loop (Build 2.7.0).
    """
    ops: ClauseOps[ClauseT, FormulaT]
    limits: SaturationLimits = field(default_factory=SaturationLimits)
    
    _active_set: set[ClauseT] = field(init=False, default_factory=set)
    _active_list: list[ClauseT] = field(init=False, default_factory=list)
    _active_prov: list[ClauseProvenance] = field(init=False, default_factory=list)
    _passive: list[tuple[int, int, ClauseT, ClauseProvenance]] = field(init=False, default_factory=list)
    _counter: itertools.count = field(init=False, default_factory=itertools.count)
    stats: SaturationStats = field(init=False, default_factory=SaturationStats)

    def push_axioms(self, axioms: Iterable[ClauseT]) -> None:
        axs = list(axioms)
        print(f"    [SATURATE] Pushing {len(axs)} axioms to passive set...")
        for i, a in enumerate(axs):
            if i % 10 == 0 and i > 0:
                print(f"      ... pushed {i} axioms")
            prov = ClauseProvenance(kind="axiom", parents=(), depth=0)
            self._push_passive(a, prov)

    def _push_passive(self, c: ClauseT, prov: ClauseProvenance) -> None:
        c = self.ops.canonicalize(c)
        if prov.depth > self.limits.max_depth: return
        if self.stats.generated >= self.limits.max_generated: return
        if len(self._passive) >= self.limits.max_passive: return
        
        # O-FLOW: Check admissibility before pushing to passive set
        if not self.ops.admissible(c, depth=prov.depth):
            return

        w = self.ops.weight(c)
        heapq.heappush(self._passive, (w, next(self._counter), c, prov))
        self.stats.admitted_passive += 1

    def run(self) -> Iterator[ClauseT]:
        while self._passive and self.stats.given_steps < self.limits.max_given_steps:
            if self.stats.generated >= self.limits.max_generated: return

            _w, _n, given, prov = heapq.heappop(self._passive)
            self.stats.given_steps += 1

            if self.ops.redundant(given, active=self._active_set):
                self.stats.redundant_skipped += 1
                continue

            if len(self._active_set) >= self.limits.max_active: return

            n_before = len(self._active_list)
            given_idx = n_before
            self._active_set.add(given)
            self._active_list.append(given)
            self._active_prov.append(prov)
            self.stats.admitted_active += 1
            
            if self.stats.admitted_active % 50 == 0:
                print(f"    [SATURATE] Admitted {self.stats.admitted_active} clauses... (Heap: {len(self._passive)})")
            
            yield given

            for i in range(n_before):
                if self.stats.generated >= self.limits.max_generated: return
                other = self._active_list[i]
                other_prov = self._active_prov[i]

                for res in self.ops.resolve(given, other):
                    self.stats.generated += 1
                    depth = max(prov.depth, other_prov.depth) + 1
                    if depth > self.limits.max_depth: continue
                    if not self.ops.admissible(res, depth=depth): continue

                    rprov = ClauseProvenance(kind="resolvent", parents=(given_idx, i), depth=depth)
                    self._push_passive(res, rprov)

@dataclass
class SaturationResult:
    generated_clauses: List[cl.Clause]
    generated_equalities: List[cl.Formula]
    stats: Dict[str, int]

class ForwardChainingSaturator:
    """Wrapper to maintain backwards compatibility with the Discovery Engine."""
    def __init__(self, max_clauses: int = 500, max_depth: int = 6, mode: str = "full"):
        self.max_clauses = max_clauses
        self.max_depth = max_depth
        self.mode = mode
    def self_mutate(self, mutation_signal: float):
        """
        UAP: Mutate Saturator parameters based on metasystem signal.
        signal > 0: increase intensity, signal < 0: decrease intensity.
        """
        if mutation_signal > 0:
            scale = 1.0 + mutation_signal
            self.max_clauses = int(self.max_clauses * scale)
            self.max_depth = min(25, self.max_depth + 1)
        else:
            scale = 1.0 + mutation_signal # mutation_signal is negative
            self.max_clauses = int(self.max_clauses * max(0.5, scale))
            
        print(f"[UAP:Saturator] Mutated. Max Clauses: {self.max_clauses}, Max Depth: {self.max_depth}")

    def saturate(self, axioms: List[cl.Formula]) -> SaturationResult:
        # 1. Initialize E-Graph and extract rewrites/demodulators
        egraph = RiskEGraph()
        rewrites = []
        demodulators = []
        all_clauses = []
        
        from discovery.normalization import (
            logic_to_egraph_term, egraph_term_to_logic, orient_rewrite
        )

        for i, ax in enumerate(axioms):
            try:
                all_clauses.extend(to_cnf(ax, source=f"ax{i}"))
                curr = ax
                while isinstance(curr, cl.Forall): curr = curr.body
                if isinstance(curr, cl.Equality):
                    et_lhs = logic_to_egraph_term(curr.left)
                    et_rhs = logic_to_egraph_term(curr.right)
                    rewrites.append(ERewrite(et_lhs, et_rhs, "ax"))
                    
                    # Build 2.9.0: Orient as directed demodulator if possible
                    oriented = orient_rewrite(et_lhs, et_rhs)
                    if oriented:
                        l, r = oriented
                        demodulators.append(ERewrite(l, r, "ax"))
            except Exception: pass
        
        saturate_with_rewrites(egraph, rewrites)
        
        # 2. Setup Hardened Saturator
        ops = OperandicsClauseOps(
            egraph=egraph, 
            max_depth=self.max_depth, 
            demodulators=demodulators,
            mode=self.mode
        )
        sat = SaturatorLoop(
            ops=ops,
            limits=SaturationLimits(
                max_depth=self.max_depth,
                max_active=self.max_clauses,
                max_generated=self.max_clauses * 20
            )
        )
        sat.push_axioms(all_clauses)
        
        # 3. Run
        generated = list(sat.run())
        
        # 4. Extract equalities
        equalities = []
        for c in generated:
            if c.is_unit():
                lit = next(iter(c.literals))
                if lit.positive and isinstance(lit.atom, (cl.Equality, cl.LessEq)):
                    equalities.append(lit.atom)
        
        return SaturationResult(
            generated_clauses=generated,
            generated_equalities=equalities,
            stats={
                "resolutions": sat.stats.generated,
                "given_steps": sat.stats.given_steps,
                "admitted": sat.stats.admitted_active
            }
        )
