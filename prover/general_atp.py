"""
prover/general_atp.py

Resolution-based theorem prover with refutation.
This is the verification backend (Component 6).
"""

from core.logic import *
import core.logic as cl
from core.unification import *
from dataclasses import dataclass, field
from enum import Enum
from typing import List, NamedTuple, Set, Optional, Tuple
import itertools
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict


@dataclass
class ProofResult:
    success: bool
    steps: int = 0
    proved_formula: Optional[Formula] = None
    proof_trace: List[str] = field(default_factory=list)
    reason: str = ""  # "PROVED", "RESOURCE_EXHAUSTION", "NO_PROOF_FOUND", "EGRAPH_NORMALIZATION"
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    applied_rules: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════
# CNF CONVERSION
# ═══════════════════════════════════════════════════

_skolem_counter = 0

def fresh_skolem(arity: int, sort: Sort = MODULE) -> str:
    global _skolem_counter
    _skolem_counter += 1
    return f"sk_{_skolem_counter}"


def eliminate_implications(formula: Formula) -> Formula:
    """Remove → by converting A → B to ¬A ∨ B."""
    if isinstance(formula, Atom) or isinstance(formula, Equality) or isinstance(formula, LessEq):
        return formula
    elif isinstance(formula, Not):
        return Not(eliminate_implications(formula.formula))
    elif isinstance(formula, And):
        return And(eliminate_implications(formula.left), eliminate_implications(formula.right))
    elif isinstance(formula, Or):
        return Or(eliminate_implications(formula.left), eliminate_implications(formula.right))
    elif isinstance(formula, Implies):
        return Or(Not(eliminate_implications(formula.antecedent)), 
                  eliminate_implications(formula.consequent))
    elif isinstance(formula, Forall):
        return Forall(formula.variable, eliminate_implications(formula.body))
    elif isinstance(formula, Exists):
        return Exists(formula.variable, eliminate_implications(formula.body))
    return formula


def push_negation_inward(formula: Formula) -> Formula:
    """Push negations inward (NNF conversion)."""
    if isinstance(formula, Atom) or isinstance(formula, Equality) or isinstance(formula, LessEq):
        return formula
    elif isinstance(formula, Not):
        inner = formula.formula
        if isinstance(inner, Not):
            return push_negation_inward(inner.formula)
        elif isinstance(inner, And):
            return Or(push_negation_inward(Not(inner.left)), 
                      push_negation_inward(Not(inner.right)))
        elif isinstance(inner, Or):
            return And(push_negation_inward(Not(inner.left)), 
                       push_negation_inward(Not(inner.right)))
        elif isinstance(inner, Forall):
            return Exists(inner.variable, push_negation_inward(Not(inner.body)))
        elif isinstance(inner, Exists):
            return Forall(inner.variable, push_negation_inward(Not(inner.body)))
        elif isinstance(inner, (Atom, Equality, LessEq)):
            return Not(inner)
        elif isinstance(inner, Implies):
            expanded = Or(Not(inner.antecedent), inner.consequent)
            return push_negation_inward(Not(expanded))
        return formula
    elif isinstance(formula, And):
        return And(push_negation_inward(formula.left), push_negation_inward(formula.right))
    elif isinstance(formula, Or):
        return Or(push_negation_inward(formula.left), push_negation_inward(formula.right))
    elif isinstance(formula, Forall):
        return Forall(formula.variable, push_negation_inward(formula.body))
    elif isinstance(formula, Exists):
        return Exists(formula.variable, push_negation_inward(formula.body))
    return formula


def skolemize(formula: Formula, universal_vars: List[Variable] = None) -> Formula:
    """Replace existential quantifiers with Skolem functions."""
    if universal_vars is None:
        universal_vars = []
    
    if isinstance(formula, Forall):
        return Forall(formula.variable, 
                      skolemize(formula.body, universal_vars + [formula.variable]))
    elif isinstance(formula, Exists):
        skolem_name = fresh_skolem(len(universal_vars), formula.variable.sort)
        if universal_vars:
            skolem_term = Function(skolem_name, tuple(universal_vars), formula.variable.sort)
        else:
            skolem_term = Constant(skolem_name, formula.variable.sort)
        new_body = formula.body.substitute({formula.variable: skolem_term})
        return skolemize(new_body, universal_vars)
    elif isinstance(formula, And):
        return And(skolemize(formula.left, universal_vars), 
                   skolemize(formula.right, universal_vars))
    elif isinstance(formula, Or):
        return Or(skolemize(formula.left, universal_vars), 
                  skolemize(formula.right, universal_vars))
    elif isinstance(formula, Not):
        return Not(skolemize(formula.formula, universal_vars))
    return formula


def drop_universals(formula: Formula) -> Formula:
    """Drop universal quantifiers (implicit in CNF)."""
    if isinstance(formula, Forall):
        return drop_universals(formula.body)
    return formula


def distribute_or_over_and(formula: Formula) -> Formula:
    """Convert to CNF by distributing ∨ over ∧."""
    if isinstance(formula, And):
        return And(distribute_or_over_and(formula.left), 
                   distribute_or_over_and(formula.right))
    elif isinstance(formula, Or):
        left = distribute_or_over_and(formula.left)
        right = distribute_or_over_and(formula.right)
        
        if isinstance(left, And):
            return And(
                distribute_or_over_and(Or(left.left, right)),
                distribute_or_over_and(Or(left.right, right))
            )
        if isinstance(right, And):
            return And(
                distribute_or_over_and(Or(left, right.left)),
                distribute_or_over_and(Or(left, right.right))
            )
        return Or(left, right)
    return formula


def formula_to_literals(formula: Formula) -> Set[Literal]:
    """Convert a disjunction of atoms/negated atoms to a set of literals."""
    if isinstance(formula, Or):
        return formula_to_literals(formula.left) | formula_to_literals(formula.right)
    elif isinstance(formula, Not):
        inner = formula.formula
        if isinstance(inner, (Atom, Equality, LessEq)):
            return {Literal(inner, False)}
        return {Literal(Atom("__raw__", ()), True)}
    elif isinstance(formula, (Atom, Equality, LessEq)):
        return {Literal(formula, True)}
    return set()


def formula_to_clauses(formula: Formula) -> List[Clause]:
    """Convert a CNF formula (conjunction of disjunctions) to clause set."""
    if isinstance(formula, And):
        return formula_to_clauses(formula.left) + formula_to_clauses(formula.right)
    else:
        lits = formula_to_literals(formula)
        if lits:
            return [Clause(frozenset(lits))]
        return []


def to_cnf(formula: Formula, source: str = "") -> List[Clause]:
    """Full CNF conversion pipeline."""
    f = eliminate_implications(formula)
    f = push_negation_inward(f)
    f = skolemize(f)
    f = drop_universals(f)
    f = distribute_or_over_and(f)
    clauses = formula_to_clauses(f)
    return [Clause(c.literals, source) for c in clauses]


def negate_formula(formula: Formula) -> Formula:
    """Negate a formula for refutation."""
    return Not(formula)


# ═══════════════════════════════════════════════════
# RESOLUTION ENGINE
# ═══════════════════════════════════════════════════

def resolve_clauses(c1: Clause, c2: Clause, step_id: str = "") -> List[Clause]:
    """
    Attempt all possible resolutions between two clauses.
    Returns list of resolvents.
    """
    c2_renamed = rename_variables(c2, step_id)
    
    resolvents = []
    
    # Standard Resolution
    for lit1 in c1.literals:
        for lit2 in c2_renamed.literals:
            if lit1.positive != lit2.positive:
                mgu = unify_atoms(lit1.atom, lit2.atom)
                if mgu is not None:
                    remaining1 = frozenset(
                        apply_substitution_to_literal(l, mgu) 
                        for l in c1.literals if l != lit1
                    )
                    remaining2 = frozenset(
                        apply_substitution_to_literal(l, mgu) 
                        for l in c2_renamed.literals if l != lit2
                    )
                    resolvent = Clause(
                        remaining1 | remaining2,
                        f"Res({c1.source},{c2_renamed.source})"
                    )
                    if not is_tautology(resolvent):
                        resolvents.append(resolvent)
    
    # Reflexivity Resolution (implicitly resolve against x=x)
    # Check if c1 contains t != t' where t, t' unify
    for lit in c1.literals:
        if not lit.positive and isinstance(lit.atom, Equality):
            mgu = unify_terms(lit.atom.left, lit.atom.right)
            if mgu is not None:
                # This literal is FALSE under mgu, so we can remove it
                remaining = frozenset(
                    apply_substitution_to_literal(l, mgu)
                    for l in c1.literals if l != lit
                )
                resolvent = Clause(remaining, f"Refl({c1.source})")
                if not is_tautology(resolvent):
                    resolvents.append(resolvent)

    # Note: We typically don't need to check c2 for reflexivity here because 
    # it would have been processed when it was the 'given' clause. 
    # But for completeness/safety in this loop structure:
    for lit in c2_renamed.literals:
         if not lit.positive and isinstance(lit.atom, Equality):
            mgu = unify_terms(lit.atom.left, lit.atom.right)
            if mgu is not None:
                remaining = frozenset(
                    apply_substitution_to_literal(l, mgu)
                    for l in c2_renamed.literals if l != lit
                )
                resolvent = Clause(remaining, f"Refl({c2_renamed.source})")
                if not is_tautology(resolvent):
                    resolvents.append(resolvent)
    
    return resolvents


def is_tautology(clause: Clause) -> bool:
    """Check if clause contains complementary literals."""
    for lit in clause.literals:
        comp = lit.negate()
        if comp in clause.literals:
            return True
    return False


def subsumes(c1: Clause, c2: Clause) -> bool:
    """Check if c1 subsumes c2 (c1 is more general)."""
    if len(c1.literals) > len(c2.literals):
        return False
    c1_strs = {str(l) for l in c1.literals}
    c2_strs = {str(l) for l in c2.literals}
    return c1_strs.issubset(c2_strs)





# ═══════════════════════════════════════════════════
# EQUATIONAL REASONING (Paramodulation)
# ═══════════════════════════════════════════════════

def find_equality_literals(clause: Clause) -> List[Tuple[Literal, Term, Term]]:
    """Find all positive equality literals in a clause."""
    results = []
    for lit in clause.literals:
        if lit.positive and isinstance(lit.atom, Equality):
            results.append((lit, lit.atom.left, lit.atom.right))
    return results


def replace_subterm(term: Term, target: Term, replacement: Term, 
                    subst: Dict[Variable, Term]) -> Optional[Tuple[Term, Dict[Variable, Term]]]:
    """Try to replace target in term using unification."""
    mgu = unify_terms(target, term, dict(subst))
    if mgu is not None:
        return (apply_substitution(replacement, mgu), mgu)
    
    if isinstance(term, Function):
        for i, arg in enumerate(term.args):
            result = replace_subterm(arg, target, replacement, subst)
            if result is not None:
                new_term, new_subst = result
                new_args = list(term.args)
                new_args[i] = new_term
                return (Function(term.symbol, tuple(new_args), term.sort), new_subst)
    
    return None


def paramodulate(c1: Clause, c2: Clause, step_id: str = "") -> List[Clause]:
    """
    Paramodulation: use equalities in c1 to rewrite terms in c2.
    Essential for equational reasoning.
    """
    c2_renamed = rename_variables(c2, step_id)
    results = []
    
    for eq_lit, lhs, rhs in find_equality_literals(c1):
        for lit2 in c2_renamed.literals:
            if isinstance(lit2.atom, (Atom, Equality, LessEq)):
                for direction in [(lhs, rhs), (rhs, lhs)]:
                    source, target = direction
                    new_atom = _try_paramodulate_atom(lit2.atom, source, target)
                    if new_atom is not None:
                        remaining1 = frozenset(l for l in c1.literals if l != eq_lit)
                        remaining2 = frozenset(
                            l if l != lit2 else Literal(new_atom, lit2.positive) 
                            for l in c2_renamed.literals
                        )
                        result = Clause(remaining1 | remaining2, f"Para({step_id})")
                        if not is_tautology(result):
                            results.append(result)
    return results


def _try_paramodulate_atom(atom: Formula, source: Term, replacement: Term) -> Optional[Formula]:
    """Try to rewrite source to replacement within an atom (deep)."""
    # Helper to wrap replace_subterm
    def try_replace(t: Term) -> Optional[Term]:
        res = replace_subterm(t, source, replacement, {})
        if res:
            return res[0] # Return new term, ignore subst for now as we apply mgu later? 
            # Wait, replace_subterm returns (new_term, mgu). 
            # We need to ensure the mgu is consistent? 
            # Actually, standard paramodulation: 
            # 1. Unify source with subterm `t|_p`. MGU `sigma`.
            # 2. Result is `(atom[replacement]_p)sigma`.
            # replace_subterm does exactly this: finds unification, applies it to replacement, 
            # and returns the new term WITH the substitution applied to it.
        return None

    if isinstance(atom, Equality):
        # Try left
        res = replace_subterm(atom.left, source, replacement, {})
        if res:
            new_left, mgu = res
            # Apply mgu to the OTHER side too!
            new_right = apply_substitution(atom.right, mgu)
            return Equality(new_left, new_right)
        
        # Try right
        res = replace_subterm(atom.right, source, replacement, {})
        if res:
            new_right, mgu = res
            new_left = apply_substitution(atom.left, mgu)
            return Equality(new_left, new_right)
            
    elif isinstance(atom, Atom):
        for i, arg in enumerate(atom.args):
            res = replace_subterm(arg, source, replacement, {})
            if res:
                new_arg, mgu = res
                new_args = [apply_substitution(a, mgu) for a in atom.args]
                new_args[i] = new_arg
                return Atom(atom.predicate, tuple(new_args))
                
    return None


# ═══════════════════════════════════════════════════
# THE PROVER
# ═══════════════════════════════════════════════════

class ResolutionEngine:
    """
    Resolution + Paramodulation prover using refutation.
    Component 6 in the nine-component architecture.
    """
    
    def __init__(self):
        self.axioms: List[Formula] = []
        self._axiom_clauses: List[Clause] = []
        self._egraph_normalization_enabled = True
    
    def add_axiom(self, formula: Formula):
        self.axioms.append(formula)
        new_clauses = to_cnf(formula, source=f"axiom_{len(self.axioms)}")
        self._axiom_clauses.extend(new_clauses)
    
    def self_mutate(self, mutation_signal: float):
        """
        UAP: Mutate ATP parameters based on metasystem signal.
        signal > 0: increase intensity, signal < 0: decrease intensity.
        """
        # Note: we don't have max_steps/age_weight_ratio as instance vars yet, 
        # normally they are passed to prove(). But we can store offsets.
        if not hasattr(self, "_steps_offset"): self._steps_offset = 0
        if not hasattr(self, "_ratio_offset"): self._ratio_offset = 0
        
        self._steps_offset += int(mutation_signal * 500)
        self._ratio_offset += int(mutation_signal * 2)
        print(f"[UAP:ATP] Mutated. Steps Offset: {self._steps_offset}, Ratio Offset: {self._ratio_offset}")
    
    def prove(self, goal: Formula, max_steps: int = 3000, 
              timeout_seconds: float = 30.0) -> ProofResult:
        """
        Prove goal by refutation with goal-directed clause selection.
        1. Negate the goal
        2. Add to axiom clauses 
        3. Derive empty clause → goal is proved
        
        Uses goal-symbol weighting: clauses sharing symbols with the
        negated goal are selected earlier, dramatically improving
        multi-step chain proofs.
        """
        import time
        start = time.time()
        
        negated = negate_formula(goal)
        goal_clauses = to_cnf(negated, source="negated_goal")
        
        # Extract goal-relevant function symbols for directed search
        goal_symbols = set()
        self._collect_symbols(goal, goal_symbols)
        
        all_clauses = list(self._axiom_clauses) + goal_clauses
        
        processed: Set[Clause] = set()
        unprocessed: List[Clause] = list(all_clauses)
        

        
        proof_trace = []
        step = 0
        
        # Age/Weight given clause ratio (e.g. 1 age per 4 weight)
        age_weight_ratio = 4
        
        # UAP: Apply mutated offsets
        actual_max_steps = max_steps + getattr(self, "_steps_offset", 0)
        actual_ratio = age_weight_ratio + getattr(self, "_ratio_offset", 0)
        actual_ratio = max(1, actual_ratio)
        
        while unprocessed and step < actual_max_steps:
            if time.time() - start > timeout_seconds:
                return ProofResult(
                    success=False, steps=step,
                    proved_formula=goal,
                    proof_trace=proof_trace,
                    reason="RESOURCE_EXHAUSTION"
                )
            
            if step % actual_ratio == 0:
                # Age Selection: Oldest clause (FIFO)
                given = unprocessed[0]
            else:
                # Weight Selection: Smallest / Goal-directed clause
                given = self._select_clause_directed(unprocessed, goal_symbols)
                
            unprocessed.remove(given)
            
            if given in processed:
                continue
            
            if given.is_empty():
                proof_trace.append(f"Step {step}: EMPTY CLAUSE derived -> PROVED")
                return ProofResult(
                    success=True, steps=step,
                    proved_formula=goal,
                    proof_trace=proof_trace,
                    reason="PROVED"
                )
            
            new_clauses = []
            for existing in processed:
                step += 1
                step_id = f"s{step}"
                
                resolvents = resolve_clauses(given, existing, step_id)
                new_clauses.extend(resolvents)
                
                paras = paramodulate(given, existing, step_id)
                new_clauses.extend(paras)
                paras2 = paramodulate(existing, given, f"{step_id}r")
                new_clauses.extend(paras2)
            
            for nc in new_clauses:
                if nc.is_empty():
                    proof_trace.append(f"Step {step}: EMPTY CLAUSE derived -> PROVED")
                    return ProofResult(
                        success=True, steps=step,
                        proved_formula=goal,
                        proof_trace=proof_trace,
                        reason="PROVED"
                    )
                # Fast forward subsumption
                is_subsumed = any(subsumes(p, nc) for p in processed)
                if nc not in processed and not is_subsumed:
                    unprocessed.append(nc)
            
            processed.add(given)
            
            if step % 100 == 0:
                proof_trace.append(f"Step {step}: {len(processed)} processed, {len(unprocessed)} unprocessed")
        
        return ProofResult(
            success=False, steps=step,
            proved_formula=goal,
            proof_trace=proof_trace,
            reason="NO_PROOF_FOUND" if step >= max_steps else "EXHAUSTED"
        )
    
    def _collect_risk_terms(self, node: Any, terms: Set[Term]):
        """Helper to collect Risk terms for diagnostics."""
        if isinstance(node, Function):
            if node.symbol == "Risk":
                terms.add(node)
            for arg in node.args:
                self._collect_risk_terms(arg, terms)
        elif hasattr(node, '__dict__'):
            for v in vars(node).values():
                if isinstance(v, (Term, Formula, list, tuple)):
                    self._collect_risk_terms(v, terms)
        elif isinstance(node, (list, tuple)):
            for item in node:
                self._collect_risk_terms(item, terms)
    def _collect_symbols(self, formula: Any, symbols: Set[str]):
        """Recursively collect function/constant symbols from a formula."""
        if isinstance(formula, cl.Function):
            symbols.add(formula.symbol)
            for arg in formula.args:
                self._collect_symbols(arg, symbols)
        elif isinstance(formula, Constant):
            symbols.add(formula.name)
        elif isinstance(formula, Equality):
            self._collect_symbols(formula.left, symbols)
            self._collect_symbols(formula.right, symbols)
        elif isinstance(formula, (Forall, Exists)):
            self._collect_symbols(formula.body, symbols)
        elif isinstance(formula, Not):
            self._collect_symbols(formula.formula, symbols)
        elif isinstance(formula, (And, Or)):
            self._collect_symbols(formula.left, symbols)
            self._collect_symbols(formula.right, symbols)
        elif isinstance(formula, Implies):
            self._collect_symbols(formula.antecedent, symbols)
            self._collect_symbols(formula.consequent, symbols)
        elif isinstance(formula, Atom):
            for arg in formula.args:
                self._collect_symbols(arg, symbols)
        elif isinstance(formula, LessEq):
            self._collect_symbols(formula.left, symbols)
            self._collect_symbols(formula.right, symbols)
        elif isinstance(formula, Literal):
            self._collect_symbols(formula.atom, symbols)
        elif isinstance(formula, Clause):
            for lit in formula.literals:
                self._collect_symbols(lit, symbols)
    
    def _select_clause_directed(self, unprocessed: List[Clause], 
                                  goal_symbols: set) -> Clause:
        """Goal-directed clause selection: prefer smaller clauses that
        share symbols with the goal."""
        def score(c: Clause) -> float:
            base = c.size()
            # Count how many goal symbols appear in this clause
            clause_syms = set()
            self._collect_symbols(c, clause_syms)
            overlap = len(clause_syms & goal_symbols)
            # Bonus for goal-relevant clauses (lower score = higher priority)
            if overlap > 0:
                return base * (0.5 / (1 + overlap))
            return base
        return min(unprocessed, key=score)
    
    def _select_clause(self, unprocessed: List[Clause]) -> Clause:
        """Select lightest clause (Given Clause selection)."""
        return min(unprocessed, key=lambda c: c.size())
    
    def reset(self):
        self.axioms.clear()
        self._axiom_clauses.clear()

class ProverStrategy(Enum):
    EGRAPH_ONLY = "egraph"
    RESOLUTION_ONLY = "resolution"
    EGRAPH_THEN_RESOLUTION = "egraph_then_resolution"

class GoalClassification(NamedTuple):
    is_equational: bool
    eq_depth: int
    quant_depth: int

class GeneralATP:
    def __init__(self, strategy: ProverStrategy = ProverStrategy.EGRAPH_THEN_RESOLUTION):
        from discovery.normalization import RiskEGraph
        self.strategy = strategy
        self.egraph = RiskEGraph()
        self.resolution_engine = ResolutionEngine()

    def add_axiom(self, formula: Formula):
        self.resolution_engine.add_axiom(formula)

    def prove(self, conjecture: Formula, kb) -> ProofResult:
        if self.strategy == ProverStrategy.EGRAPH_THEN_RESOLUTION:
            return self._layered_prove(conjecture, kb)
        elif self.strategy == ProverStrategy.EGRAPH_ONLY:
            return self._egraph_prove(conjecture, kb)
        else:
            return self._resolution_prove(conjecture, kb)

    def _layered_prove(self, conjecture: Formula, kb):
        classification = self._classify_goal(conjecture)

        if classification.is_equational:
            result = self._egraph_prove(conjecture, kb)
            if result.success or result.reason == "EGRAPH_NORMALIZATION":
                return result

        return self._resolution_prove(conjecture, kb)

    def _classify_goal(self, conjecture: Formula) -> GoalClassification:
        # Simple structural analysis
        # Count quantifier depth
        q_depth = 0
        curr = conjecture
        while isinstance(curr, (cl.Forall, cl.Exists)):
            q_depth += 1
            curr = curr.body
            
        is_eq = isinstance(curr, cl.Equality)
        eq_depth = 1 if is_eq else 0
        
        return GoalClassification(
            is_equational=(is_eq and q_depth <= 1),
            eq_depth=eq_depth,
            quant_depth=q_depth
        )

    def _egraph_prove(self, conjecture: Formula, kb) -> ProofResult:
        from discovery.normalization import (
            extract_risk_subterms, logic_to_egraph_term, 
            ERewrite, saturate_with_rewrites
        )
        
        target_goal = conjecture
        while isinstance(target_goal, cl.Forall):
            target_goal = target_goal.body
            
        if not isinstance(target_goal, cl.Equality):
            return ProofResult(success=False, reason="NOT_EQUATIONAL")
            
        def complexity(term):
            if isinstance(term, cl.Variable) or isinstance(term, cl.Constant): return 1
            if isinstance(term, cl.Function):
                return 1 + sum(complexity(a) for a in term.args)
            return 1
            
        rewrites = []
        ax_names = getattr(kb, 'axiom_names', [])
        
        for i, item in enumerate(kb.axioms):
            curr = item
            name = ax_names[i] if i < len(ax_names) else f"axiom_{i}"
            while isinstance(curr, cl.Forall):
                curr = curr.body
            if isinstance(curr, cl.Equality):
                l_term, r_term = curr.left, curr.right
                if complexity(l_term) >= complexity(r_term):
                    lhs, rhs = l_term, r_term
                else:
                    lhs, rhs = r_term, l_term
                rewrites.append(ERewrite(
                    lhs=logic_to_egraph_term(lhs),
                    rhs=logic_to_egraph_term(rhs),
                    name=name
                ))
                
        for i, item in enumerate(kb.theorems):
            curr = item
            name = f"thm_{i}"
            while isinstance(curr, cl.Forall):
                curr = curr.body
            if isinstance(curr, cl.Equality):
                l_term, r_term = curr.left, curr.right
                if complexity(l_term) >= complexity(r_term):
                    lhs, rhs = l_term, r_term
                else:
                    lhs, rhs = r_term, l_term
                rewrites.append(ERewrite(
                    lhs=logic_to_egraph_term(lhs),
                    rhs=logic_to_egraph_term(rhs),
                    name=name
                ))
                
        # Add risk terms
        all_logic_terms = extract_risk_subterms(conjecture)
        for ax in kb.axioms + kb.theorems:
            all_logic_terms.extend(extract_risk_subterms(ax))
            
        for lt in set(all_logic_terms):
            self.egraph.add(logic_to_egraph_term(lt))
            
        l_id = self.egraph.add(logic_to_egraph_term(target_goal.left))
        r_id = self.egraph.add(logic_to_egraph_term(target_goal.right))
        
        _, applied = saturate_with_rewrites(self.egraph, rewrites)
        
        if self.egraph.find(l_id) == self.egraph.find(r_id):
            return ProofResult(
                success=True, steps=0,
                proved_formula=conjecture,
                proof_trace=["Equivalence established in E-Graph via rewrite."],
                applied_rules=applied,
                reason="EGRAPH_NORMALIZATION"
            )
            
        return ProofResult(success=False, reason="EGRAPH_FAILED")

    def _resolution_prove(self, conjecture: Formula, kb) -> ProofResult:
        # Load axioms into the resolution engine dynamically
        self.resolution_engine.axioms = []
        self.resolution_engine._axiom_clauses = []
        # Support both 'theorems' (KnowledgeBase snapshot) and 'lemmas' (Explorer instance)
        theorems = getattr(kb, 'theorems', getattr(kb, 'lemmas', []))
        for ax in kb.axioms + theorems:
            self.resolution_engine.add_axiom(ax)
        return self.resolution_engine.prove(conjecture)
