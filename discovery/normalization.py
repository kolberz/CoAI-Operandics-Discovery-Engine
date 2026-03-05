"""
discovery/normalization.py

Robust E-Graph normalization for Risk expressions.
Bridges the gap between symbolic discovery and deductive proof.
Supports congruence closure with 'repair' and C-1 contextual congruence.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any, Iterator, Mapping, Sequence
from collections import defaultdict, deque
import core.logic as cl
import re

# Pre-compiled regex for sort inference
P_VAR_RE = re.compile(r"^P\d+$")
PROB_VAR_RE = re.compile(r"^PROB_")
REAL_CONST_RE = re.compile(r"^R_")
REAL_VARS = {"epsilon", "tau", "delta", "gamma", "N", "e_hat"}
REAL_CONSTS = {"R_ZERO", "R_ONE", "R_INF", "R_PENALTY", "ZERO_J", "ZERO_bit", "LANDAUER", "DEP_ZERO", "DEP_ONE"}

def get_eterm_sort(t: ETerm) -> cl.Sort:
    """Infers the sort of an ETerm using heuristics and signatures."""
    from core.logic import OPERAD_SIGNATURES, MODULE, REAL, PROB, PRED
    
    if isinstance(t, EVar):
        name = t.name
        if name == "P" or P_VAR_RE.match(name): return PRED
        if name.startswith("prob") or name == "p":
            return PRED if name == "p" else PROB
        if name.startswith("R") or name in REAL_VARS: return REAL
        return MODULE
        
    if isinstance(t, ESym):
        name = t.name
        sig = OPERAD_SIGNATURES.get(name)
        if sig: return sig.result_sort
        if name == "P_TRUE": return PRED
        if REAL_CONST_RE.match(name) or name in REAL_CONSTS: return REAL
        if PROB_VAR_RE.match(name): return PROB
        return MODULE
        
    if isinstance(t, EApp):
        sig = OPERAD_SIGNATURES.get(t.op)
        return sig.result_sort if sig else MODULE
        
    return MODULE

# =============================================================================
# 1) Internal Term AST + Pattern Matching
# =============================================================================

class ETerm: pass

@dataclass(frozen=True, slots=True)
class EVar(ETerm):
    name: str

@dataclass(frozen=True, slots=True)
class ESym(ETerm):
    name: str

@dataclass(frozen=True, slots=True)
class EApp(ETerm):
    op: str
    args: Tuple[ETerm, ...]

def ematch(pattern: ETerm, ground: ETerm, env: Dict[str, ETerm]) -> bool:
    """Pattern match (not full unification). Pattern may contain EVar."""
    if isinstance(pattern, EVar):
        bound = env.get(pattern.name)
        if bound is None:
            env[pattern.name] = ground
            return True
        return bound == ground

    if type(pattern) is not type(ground):
        return False

    if isinstance(pattern, ESym):
        return pattern.name == ground.name

    if isinstance(pattern, EApp):
        g = ground
        if pattern.op != g.op or len(pattern.args) != len(g.args):
            return False
        for pa, ga in zip(pattern.args, g.args):
            if not ematch(pa, ga, env):
                return False
        return True
    return False

def esubst(term: ETerm, env: Mapping[str, ETerm]) -> ETerm:
    """Instantiate a pattern term using bindings in env."""
    if isinstance(term, EVar):
        return env.get(term.name, term)
    if isinstance(term, ESym):
        return term
    if isinstance(term, EApp):
        return EApp(term.op, tuple(esubst(a, env) for a in term.args))
    raise TypeError(f"Unknown Term type: {type(term)}")

# =============================================================================
# 2) E-Graph Core (with Repair and C-1 Logic)
# =============================================================================

@dataclass(frozen=True, slots=True)
class ENode:
    op: str
    children: Tuple[int, ...]  # e-class ids (roots)

# =============================================================================
# 1.1) Term Complexity and Ordering (Build 2.9.0)
# =============================================================================

def eterm_size(t: ETerm) -> int:
    if isinstance(t, (EVar, ESym)): return 1
    if isinstance(t, EApp): return 1 + sum(eterm_size(a) for a in t.args)
    return 1

def eterm_key(t: ETerm) -> tuple[int, str]:
    """Stable total order for tie-breaking rewrites."""
    return (eterm_size(t), str(t))

def orient_rewrite(lhs: ETerm, rhs: ETerm) -> Optional[tuple[ETerm, ETerm]]:
    """Orient into a reducing rule. Returns (heavier, lighter) or None."""
    k1, k2 = eterm_key(lhs), eterm_key(rhs)
    if k1 > k2: return (lhs, rhs)
    if k2 > k1: return (rhs, lhs)
    return None

def normalize_innermost(t: ETerm, rules: Sequence[ERewrite], max_steps: int = 100) -> ETerm:
    """Innermost (bottom-up) rewriting loop for demodulation."""
    curr = t
    for _ in range(max_steps):
        nxt = _rewrite_one_step(curr, rules)
        if nxt is None: return curr
        curr = nxt
    return curr

def _rewrite_one_step(t: ETerm, rules: Sequence[ERewrite]) -> Optional[ETerm]:
    # 1. Rewrite children first
    if isinstance(t, EApp):
        for i, arg in enumerate(t.args):
            ra = _rewrite_one_step(arg, rules)
            if ra is not None:
                new_args = list(t.args)
                new_args[i] = ra
                return EApp(t.op, tuple(new_args))
    
    # 2. Rewrite root
    for rw in rules:
        env: Dict[str, ETerm] = {}
        if ematch(rw.lhs, t, env):
            out = esubst(rw.rhs, env)
            if eterm_key(out) < eterm_key(t):
                return out
    return None

class RiskEGraph:
    def __init__(self) -> None:
        self._next_class: int = 0
        self._parent: dict[int, int] = {}
        self._rank: dict[int, int] = {}
        self._sort: dict[int, cl.Sort] = {} # Sort of the class
        self._enode_class: dict[ENode, int] = {}
        self._parents: dict[int, set[tuple[ENode, int]]] = defaultdict(set)
        self._term_class: dict[ETerm, int] = {}
        self._rep: dict[int, ETerm] = {}
        self.proven_unions: list[tuple[int, int]] = []

        # C-1 logic indexes
        self._risk_payload: dict[int, set[int]] = defaultdict(set)
        self._par_right_occ: dict[int, set[tuple[int, int]]] = defaultdict(set) # y_class -> (x_class, risk_class)
        self._par_left_occ: dict[int, set[tuple[int, int]]] = defaultdict(set)  # x_class -> (y_class, risk_class)
        self._barrier_true_occ: dict[int, set[int]] = defaultdict(set) # y_class -> risk_class
        self._dirty_risk_roots: set[int] = set()

    def find(self, c: int) -> int:
        while self._parent[c] != c:
            self._parent[c] = self._parent[self._parent[c]]
            c = self._parent[c]
        return c

    def _make_class(self, rep: ETerm) -> int:
        c = self._next_class
        self._next_class += 1
        self._parent[c] = c
        self._rank[c] = 0
        self._sort[c] = get_eterm_sort(rep)
        self._rep[c] = rep
        return c

    def union(self, a: int, b: int) -> int:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra

        if self._sort[ra] != self._sort[rb]:
            # Refuse to merge different sorts
            return ra

        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

        self._rep.pop(rb, None) # ra is the new rep
        self.proven_unions.append((a, b))
        self._repair_after_merge(ra, rb)

        # Merge risk payloads for C-1
        if rb in self._risk_payload:
            self._risk_payload[ra].update(self._risk_payload.pop(rb))
            self._dirty_risk_roots.add(ra)
        if ra in self._risk_payload:
            self._dirty_risk_roots.add(ra)

        return ra

    def add(self, t: ETerm) -> int:
        if t in self._term_class:
            return self.find(self._term_class[t])

        if isinstance(t, ESym):
            c = self._make_class(t)
            self._term_class[t] = c
            self._intern_enode(ENode(op=f"SYM:{t.name}", children=()), c)
            self._index_term(t, c)
            return self.find(c)

        if isinstance(t, EApp):
            child_classes = tuple(self.add(a) for a in t.args)
            child_roots = tuple(self.find(c) for c in child_classes)
            en = ENode(t.op, child_roots)

            prev = self._enode_class.get(en)
            if prev is not None:
                c = self.find(prev)
                self._term_class[t] = c
                self._index_term(t, c)
                return c

            c = self._make_class(t)
            self._term_class[t] = c
            self._intern_enode(en, c)
            self._index_term(t, c)
            return self.find(c)
        
        # Treatment of EVar
        if isinstance(t, EVar):
            c = self._make_class(t)
            self._term_class[t] = c
            en = ENode(op=f"VAR:{t.name}", children=())
            self._intern_enode(en, c)
            self._index_term(t, c)
            return self.find(c)

        raise TypeError(f"Unknown Term type: {type(t)}")

    @property
    def branching_factor(self) -> float:
        """
        The average number of enodes per e-class.
        A proxy for architectural curvature/combinatorial complexity.
        """
        n_classes = len(self._parent)
        if n_classes == 0: return 1.0
        n_nodes = len(self._enode_class)
        return n_nodes / n_classes

    def _intern_enode(self, en: ENode, c: int) -> None:
        c = self.find(c)
        prev = self._enode_class.get(en)
        if prev is None:
            self._enode_class[en] = c
        else:
            self.union(c, prev)
            c = self.find(c)
        for ch in en.children:
            self._parents[self.find(ch)].add((en, c))

    def _repair_after_merge(self, kept: int, removed: int) -> None:
        work = deque()
        for cls in (kept, removed):
            for (pen, pcls) in list(self._parents.get(cls, ())):
                work.append((pen, pcls))

        while work:
            pen, pcls = work.popleft()
            pcls = self.find(pcls)
            new_children = tuple(self.find(ch) for ch in pen.children)
            new_en = ENode(pen.op, new_children)

            prev = self._enode_class.get(new_en)
            if prev is None:
                self._enode_class[new_en] = pcls
                for ch in new_children:
                    self._parents[ch].add((new_en, pcls))
            else:
                r1, r2 = self.find(pcls), self.find(prev)
                if r1 != r2:
                    self.union(r1, r2)
                    for (pp, pc) in list(self._parents.get(r1, ())):
                        work.append((pp, pc))
                    for (pp, pc) in list(self._parents.get(r2, ())):
                        work.append((pp, pc))

    def _index_term(self, t: ETerm, cls: int) -> None:
        cls = self.find(cls)
        if not (isinstance(t, EApp) and t.op == "Risk" and len(t.args) == 1):
            return

        inner = t.args[0]
        inner_cls = self.find(self.add(inner))
        self._risk_payload[cls].add(inner_cls)
        self._dirty_risk_roots.add(cls)

        if isinstance(inner, EApp) and inner.op == "Par_Dyn" and len(inner.args) == 2:
            x_cls = self.find(self.add(inner.args[0]))
            y_cls = self.find(self.add(inner.args[1]))
            self._par_right_occ[y_cls].add((x_cls, cls))
            self._par_left_occ[x_cls].add((y_cls, cls))
            self._dirty_risk_roots.add(cls)

        if (isinstance(inner, EApp) and inner.op == "Barrier" and len(inner.args) == 2 
            and isinstance(inner.args[1], ESym) and inner.args[1].name == "P_TRUE"):
            y_cls = self.find(self.add(inner.args[0]))
            self._barrier_true_occ[y_cls].add(cls)
            self._dirty_risk_roots.add(cls)

    def close_contextual_congruence(self, *, max_steps: int = 1000) -> int:
        unions_before = len(self.proven_unions)
        steps = 0
        while self._dirty_risk_roots and steps < max_steps:
            steps += 1
            r = self.find(self._dirty_risk_roots.pop())
            # Canonicalize payloads to current roots
            inners_raw = self._risk_payload.get(r, set())
            inners = {self.find(i) for i in inners_raw}
            self._risk_payload[r] = inners # Update with canonicalized set
            
            if len(inners) < 2: continue
            
            inners_list = list(inners)
            rep_inner = inners_list[0]
            rep_inner_term = self._rep[rep_inner]
            
            for inner_cls in inners_list[1:]:
                inner_term = self._rep[inner_cls]

                # C-1R: Risk(Par(X, rep)) == Risk(Par(X, inner))
                for (x_cls_raw, _risk_term_cls) in list(self._par_right_occ.get(inner_cls, ())):
                    x_cls = self.find(x_cls_raw)
                    x_term = self._rep[x_cls]
                    t_rep = EApp("Risk", (EApp("Par_Dyn", (x_term, rep_inner_term)),))
                    t_inn = EApp("Risk", (EApp("Par_Dyn", (x_term, inner_term)),))
                    self.union(self.add(t_rep), self.add(t_inn))

                # C-1L: Risk(Par(rep, X)) == Risk(Par(inner, X))
                for (y_cls_raw, _risk_term_cls) in list(self._par_left_occ.get(inner_cls, ())):
                    y_cls = self.find(y_cls_raw)
                    y_term = self._rep[y_cls]
                    t_rep = EApp("Risk", (EApp("Par_Dyn", (rep_inner_term, y_term)),))
                    t_inn = EApp("Risk", (EApp("Par_Dyn", (inner_term, y_term)),))
                    self.union(self.add(t_rep), self.add(t_inn))

                # C-1B
                if inner_cls in self._barrier_true_occ or rep_inner in self._barrier_true_occ:
                    t_rep = EApp("Risk", (EApp("Barrier", (rep_inner_term, ESym("P_TRUE"))),))
                    t_inn = EApp("Risk", (EApp("Barrier", (inner_term, ESym("P_TRUE"))),))
                    self.union(self.add(t_rep), self.add(t_inn))
            
            if r in self._risk_payload: self._dirty_risk_roots.add(r)
        return len(self.proven_unions) - unions_before

# =============================================================================
# 3) Rewrites & Saturation
# =============================================================================

@dataclass(frozen=True, slots=True)
class ERewrite:
    lhs: ETerm
    rhs: ETerm
    name: str = "rw"

def saturate_with_rewrites(e: RiskEGraph, rewrites: Sequence[ERewrite], max_iters: int = 50) -> Tuple[int, List[str]]:
    # Step 1 & 2: Define symbolic cost, interaction rank, and compute rewrite gain
    def extract_sequence_axes(t: ETerm) -> Set[str]:
        axes = set()
        if isinstance(t, EVar):
            if "i" in t.name or "j" in t.name or "k" in t.name or "n" in t.name:
                axes.add(t.name)
        elif isinstance(t, EApp):
            for a in t.args:
                axes.update(extract_sequence_axes(a))
        return axes
        
    def interaction_rank(t: ETerm) -> int:
        if isinstance(t, EApp) and t.op in {"Exp", "Log", "Attn", "Normalize", "Softmax", "Mul", "Dot"}:
            axes = extract_sequence_axes(t)
            # A simple rule: distinct interacting variables across these operators
            return len(axes)
        return 0

    def operator_weight(t: ETerm) -> float:
        if isinstance(t, EApp):
            w = 1.0
            if t.op in {"Exp", "Log", "Attn"}: w = 4.0
            elif t.op in {"Normalize", "Softmax"}: w = 6.0
            return w + sum(operator_weight(a) for a in t.args)
        return 1.0

    def cost(t: ETerm) -> float:
        # Penalize deep syntax, expensive operators, and high interaction ranks
        return eterm_size(t) + 0.5 * operator_weight(t) + 2.0 * interaction_rank(t)
        
    def gain(rw: ERewrite) -> float:
        return cost(rw.lhs) - cost(rw.rhs)

    # Step 3: Priority queue for rewrites (sorting by gain descending)
    sorted_rewrites = sorted(rewrites, key=gain, reverse=True)
    
    it = 0
    changed = True
    applied_rules = []
    MAX_EGRAPH_SIZE = 500  # Step 5: add rewrite throttling
    
    while changed and it < max_iters:
        changed = False
        it += 1
        terms = list(e._term_class.keys())
        unions_before = len(e.proven_unions)
        
        current_size = len(e._enode_class)
        
        for t in terms:
            for rw in sorted_rewrites:
                # Throttling expansive rules
                rw_gain = gain(rw)
                if rw_gain < 0 and current_size > MAX_EGRAPH_SIZE:
                    continue  # Skip expansive rules if egraph is getting too large
                    
                env: Dict[str, ETerm] = {}
                if ematch(rw.lhs, t, env):
                    t2 = esubst(rw.rhs, env)
                    c1 = e.add(t)
                    c2 = e.add(t2)
                    if e.find(c1) != e.find(c2):
                        e.union(c1, c2)
                        applied_rules.append(rw.name)
                        
        e.close_contextual_congruence()
        changed = len(e.proven_unions) != unions_before
    
    deduped = list(dict.fromkeys(applied_rules))
    return it, deduped

# =============================================================================
# 4) Formula Utilities & Conversion
# =============================================================================

def logic_to_egraph_term(term: cl.Term) -> ETerm:
    if isinstance(term, cl.Variable): return EVar(term.name)
    if isinstance(term, cl.Constant): return ESym(term.name)
    if isinstance(term, cl.Function):
        return EApp(term.symbol, tuple(logic_to_egraph_term(a) for a in term.args))
    raise TypeError(f"Cannot convert {type(term)}")

def egraph_term_to_logic(term: ETerm) -> cl.Term:
    # Use global sorts for speed
    from core.logic import OPERAD_SIGNATURES, MODULE, REAL, PROB, PRED

    if isinstance(term, EVar):
        name = term.name
        res_sort = MODULE
        if name == "P" or P_VAR_RE.match(name):
            res_sort = PRED
        elif name.startswith("prob") or name == "p":
            if name == "p": res_sort = PRED
            else: res_sort = PROB
        elif name.startswith("R") or name in REAL_VARS:
            res_sort = REAL
        return cl.Variable(name, res_sort)

    if isinstance(term, ESym):
        name = term.name
        sig = OPERAD_SIGNATURES.get(name)
        if sig:
            res_sort = sig.result_sort
        else:
            res_sort = MODULE
            if name == "P_TRUE": res_sort = PRED
            elif REAL_CONST_RE.match(name) or name in REAL_CONSTS:
                res_sort = REAL
            elif PROB_VAR_RE.match(name): res_sort = PROB
        return cl.Constant(name, res_sort)

    if isinstance(term, EApp):
        # Hot path optimization: only call egraph_term_to_logic if args exist
        args = tuple(egraph_term_to_logic(a) for a in term.args)
        sig = OPERAD_SIGNATURES.get(term.op)
        res_sort = sig.result_sort if sig else MODULE
        return cl.Function(term.op, args, res_sort)
    raise TypeError(f"Cannot convert {type(term)}")

def extract_risk_subterms(node: Any) -> List[cl.Term]:
    subterms = []
    if isinstance(node, cl.Function):
        if node.symbol == "Risk": subterms.append(node)
        for arg in node.args: subterms.extend(extract_risk_subterms(arg))
    elif isinstance(node, (cl.Forall, cl.Equality, cl.Implies, cl.And, cl.Or, cl.Not, cl.Atom, cl.LessEq, cl.Exists)):
        for v in vars(node).values():
            if isinstance(v, (cl.Term, cl.Formula)): subterms.extend(extract_risk_subterms(v))
            elif isinstance(v, (list, tuple)):
                for item in v:
                    if isinstance(item, (cl.Term, cl.Formula)): subterms.extend(extract_risk_subterms(item))
    return subterms

def normalize_trotter(term: cl.Term) -> cl.Term:
    """
    Recursively expands Trotter(...) applications into symmetric Seq(...) splits.
    Approximates e^(A+B) as e^(A/2) e^B e^(A/2).
    """
    if isinstance(term, (cl.Variable, cl.Constant)):
        return term
    
    if isinstance(term, cl.Function):
        new_args = tuple(normalize_trotter(a) for a in term.args)
        
        if term.symbol == "Trotter":
            # 2nd order Trotter-Suzuki: e^(A+B) approx e^(A/2) e^B e^(A/2)
            # For n args: Trotter(A, B, C) -> Seq(Half(A), Half(B), C, Half(B), Half(A))
            if len(new_args) < 1:
                return cl.Constant("ID_M", cl.MODULE)
            if len(new_args) == 1:
                return new_args[0]
            
            # Recursive symmetric expansion
            # Trotter(A, B) -> Seq(Half(A), B, Half(A))
            # Trotter(A, B, C) -> Seq(Half(A), Trotter(B, C), Half(A))
            a, rest = new_args[0], new_args[1:]
            inner = rest[0] if len(rest) == 1 else cl.Function("Trotter", rest, cl.MODULE)
            inner_norm = normalize_trotter(inner)
            
            return cl.Function("Seq", (cl.Function("Half", (a,), cl.MODULE), inner_norm, cl.Function("Half", (a,), cl.MODULE)), cl.MODULE)

        return cl.Function(term.symbol, new_args, term.sort)
    
    return term
