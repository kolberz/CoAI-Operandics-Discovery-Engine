"""
grounding/dim_constraints.py

Constraint-based dimensional inference engine for Gate 3.

Architecture:
  1) alpha_rename()       -- scopes bound variables per axiom
  2) ConstraintCollector  -- builds linear constraints over Z^3
  3) solve_constraints()  -- Gaussian elimination over Q (no Z3)

Handles: Equality, LessEq, plus/minus/max/min, times/divide.

Note: Uses deferred imports from grounding.dimensions to avoid
circular import (dimensions.py imports from this module).
"""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from core.logic import (
    Term, Variable, Constant, Function,
    Formula, Atom, Equality, LessEq,
    Not, And, Or, Implies, Forall, Exists,
)

if TYPE_CHECKING:
    from grounding.dimensions import Dimension, DimensionRegistry


# =============================================
# LAZY IMPORTS (breaks circular dependency)
# =============================================

def _get_dimensionless():
    """Lazily import DIMENSIONLESS to avoid circular import."""
    from grounding.dimensions import DIMENSIONLESS
    return DIMENSIONLESS


def _is_non_numeric(sort) -> bool:
    """Lazily delegate to dimensions._is_non_numeric_sort."""
    from grounding.dimensions import _is_non_numeric_sort
    return _is_non_numeric_sort(sort)


# =============================================
# DimExpr: LINEAR DIMENSION EXPRESSION
# =============================================

@dataclass(frozen=True)
class DimExpr:
    """
    Linear form over dimension variables:
      sum_i(coeffs[var_i] * dim(var_i)) + const

    For additive ops:  dim(a) must == dim(b), output = dim(a)
    For times(a, b):   output = DimExpr(a).add(DimExpr(b))
    For divide(a, b):  output = DimExpr(a).sub(DimExpr(b))

    The const field uses Dimension exponent arithmetic
    (* = add exponents, / = subtract exponents).
    """
    coeffs: Dict[str, int]
    const: "Dimension"

    @staticmethod
    def zero() -> DimExpr:
        return DimExpr({}, _get_dimensionless())

    @staticmethod
    def from_var(name: str) -> DimExpr:
        return DimExpr({name: 1}, _get_dimensionless())

    @staticmethod
    def from_const(dim: "Dimension") -> DimExpr:
        return DimExpr({}, dim)

    def add(self, other: DimExpr) -> DimExpr:
        """Multiplicative dim combination: exponent addition."""
        coeffs = dict(self.coeffs)
        for k, v in other.coeffs.items():
            coeffs[k] = coeffs.get(k, 0) + v
            if coeffs[k] == 0:
                del coeffs[k]
        return DimExpr(coeffs, self.const * other.const)

    def sub(self, other: DimExpr) -> DimExpr:
        """Multiplicative dim division: exponent subtraction."""
        coeffs = dict(self.coeffs)
        for k, v in other.coeffs.items():
            coeffs[k] = coeffs.get(k, 0) - v
            if coeffs[k] == 0:
                del coeffs[k]
        return DimExpr(coeffs, self.const / other.const)


# =============================================
# CONSTRAINT
# =============================================

@dataclass(frozen=True)
class Constraint:
    """Dimensional constraint: lhs and rhs must have same dimension."""
    lhs: DimExpr
    rhs: DimExpr
    axiom: str
    path: str
    kind: str  # "eq", "le_dim_eq", "add_compat"


# =============================================
# ALPHA RENAMING
# =============================================

def alpha_rename(formula: Formula, axiom_id: str) -> Formula:
    """
    Rename Forall/Exists-bound variables so the same name in
    different axioms never unifies globally.
    """
    counter = [0]
    env: Dict[Tuple[str, object], Variable] = {}

    def rename_var(v: Variable) -> Variable:
        counter[0] += 1
        return Variable(
            name=f"{v.name}@{axiom_id}#{counter[0]}",
            sort=v.sort,
        )

    def map_term(t: Term) -> Term:
        if isinstance(t, Variable):
            return env.get((t.name, t.sort), t)
        if isinstance(t, Constant):
            return t
        if isinstance(t, Function):
            return Function(
                symbol=t.symbol,
                args=tuple(map(map_term, t.args)),
                sort=t.sort,
            )
        return t

    def map_formula(f: Formula) -> Formula:
        if isinstance(f, Atom):
            return Atom(
                predicate=f.predicate,
                args=tuple(map(map_term, f.args)),
            )
        if isinstance(f, Equality):
            return Equality(
                left=map_term(f.left),
                right=map_term(f.right),
            )
        if isinstance(f, LessEq):
            return LessEq(
                left=map_term(f.left),
                right=map_term(f.right),
            )
        if isinstance(f, Not):
            return Not(formula=map_formula(f.formula))
        if isinstance(f, And):
            return And(
                left=map_formula(f.left),
                right=map_formula(f.right),
            )
        if isinstance(f, Or):
            return Or(
                left=map_formula(f.left),
                right=map_formula(f.right),
            )
        if isinstance(f, Implies):
            return Implies(
                antecedent=map_formula(f.antecedent),
                consequent=map_formula(f.consequent),
            )
        if isinstance(f, Forall):
            saved = env.get((f.variable.name, f.variable.sort))
            newv = rename_var(f.variable)
            env[(f.variable.name, f.variable.sort)] = newv
            body = map_formula(f.body)
            if saved is not None:
                env[(f.variable.name, f.variable.sort)] = saved
            else:
                env.pop((f.variable.name, f.variable.sort), None)
            return Forall(variable=newv, body=body)
        if isinstance(f, Exists):
            saved = env.get((f.variable.name, f.variable.sort))
            newv = rename_var(f.variable)
            env[(f.variable.name, f.variable.sort)] = newv
            body = map_formula(f.body)
            if saved is not None:
                env[(f.variable.name, f.variable.sort)] = saved
            else:
                env.pop((f.variable.name, f.variable.sort), None)
            return Exists(variable=newv, body=body)
        return f

    return map_formula(formula)


# =============================================
# CONSTRAINT COLLECTOR
# =============================================

class ConstraintCollector:
    """
    Traverses axiom ASTs and builds linear dimensional constraints.

    Handles:
      - Equality/LessEq -> dim(lhs) == dim(rhs)
      - plus/minus/max/min -> additive compatibility
      - times(a, b) -> dim(output) = dim(a) + dim(b)
      - divide(a, b) -> dim(output) = dim(a) - dim(b)
    """

    def __init__(self, registry: "DimensionRegistry"):
        self.reg = registry
        self.constraints: List[Constraint] = []
        self.unknown_constants: Set[str] = set()
        self.unhandled_terms: Set[str] = set()

    def dimexpr(self, t: Term, axiom: str,
                path: str) -> Optional[DimExpr]:
        """Build a DimExpr for a term, or None if dim is N/A."""

        # -- Variables --
        if isinstance(t, Variable):
            if _is_non_numeric(t.sort):
                return None
            return DimExpr.from_var(t.name)

        # -- Constants --
        if isinstance(t, Constant):
            if _is_non_numeric(t.sort):
                return None
            d = self.reg.get_const_dim(t.name)
            if d is None:
                self.unknown_constants.add(t.name)
                return None
            return DimExpr.from_const(d)

        # -- Functions --
        if isinstance(t, Function):
            # Known output dimension (measured quantities)
            out = self.reg.output_dims.get(t.symbol)
            if out is not None:
                return DimExpr.from_const(out)

            # Additive operators
            if t.symbol in ("plus", "minus", "max", "min"):
                if len(t.args) != 2:
                    self.unhandled_terms.add(f"{t.symbol}/arity")
                    return None
                a = self.dimexpr(t.args[0], axiom,
                                 path + f".{t.symbol}[0]")
                b = self.dimexpr(t.args[1], axiom,
                                 path + f".{t.symbol}[1]")
                if a is None or b is None:
                    return None
                self.constraints.append(Constraint(
                    a, b, axiom, path, kind="add_compat"))
                return a

            # Multiplicative
            if t.symbol == "times":
                if len(t.args) != 2:
                    self.unhandled_terms.add("times/arity")
                    return None
                a = self.dimexpr(t.args[0], axiom,
                                 path + ".times[0]")
                b = self.dimexpr(t.args[1], axiom,
                                 path + ".times[1]")
                if a is None or b is None:
                    return None
                return a.add(b)

            if t.symbol == "divide":
                if len(t.args) != 2:
                    self.unhandled_terms.add("divide/arity")
                    return None
                a = self.dimexpr(t.args[0], axiom,
                                 path + ".divide[0]")
                b = self.dimexpr(t.args[1], axiom,
                                 path + ".divide[1]")
                if a is None or b is None:
                    return None
                return a.sub(b)

            # MODULE-level operators (Seq, Par_Dyn, etc.)
            if t.symbol in self.reg.output_dims:
                return None

            self.unhandled_terms.add(t.symbol)
            return None

        return None

    def collect_formula(self, f: Formula, axiom: str,
                        path: str) -> None:
        """Recursively collect dimensional constraints."""

        if isinstance(f, Equality):
            a = self.dimexpr(f.left, axiom, path + ".eq.L")
            b = self.dimexpr(f.right, axiom, path + ".eq.R")
            if a is not None and b is not None:
                self.constraints.append(Constraint(
                    a, b, axiom, path, kind="eq"))
            return

        if isinstance(f, LessEq):
            a = self.dimexpr(f.left, axiom, path + ".le.L")
            b = self.dimexpr(f.right, axiom, path + ".le.R")
            if a is not None and b is not None:
                self.constraints.append(Constraint(
                    a, b, axiom, path, kind="le_dim_eq"))
            return

        if isinstance(f, Atom):
            for i, t in enumerate(f.args):
                self.dimexpr(t, axiom,
                             path + f".atom.{f.predicate}[{i}]")
            return

        if isinstance(f, Not):
            self.collect_formula(f.formula, axiom, path + ".not")
        elif isinstance(f, And):
            self.collect_formula(f.left, axiom, path + ".and.L")
            self.collect_formula(f.right, axiom, path + ".and.R")
        elif isinstance(f, Or):
            self.collect_formula(f.left, axiom, path + ".or.L")
            self.collect_formula(f.right, axiom, path + ".or.R")
        elif isinstance(f, Implies):
            self.collect_formula(f.antecedent, axiom,
                                 path + ".implies.if")
            self.collect_formula(f.consequent, axiom,
                                 path + ".implies.then")
        elif isinstance(f, Forall):
            self.collect_formula(
                f.body, axiom,
                path + f".forall({f.variable.name})")
        elif isinstance(f, Exists):
            self.collect_formula(
                f.body, axiom,
                path + f".exists({f.variable.name})")


# =============================================
# GAUSSIAN ELIMINATION SOLVER OVER Q
# =============================================

@dataclass
class SolveResult:
    """Result of constraint solving."""
    resolved: Dict[str, "Dimension"]
    free_vars: Set[str]
    inconsistent: bool
    conflicts: List[Tuple[str, str]]

    @property
    def all_vars(self) -> Set[str]:
        return set(self.resolved.keys()) | self.free_vars


def solve_constraints(constraints: List[Constraint]) -> SolveResult:
    """
    Solve dimensional constraints via Gaussian elimination over Q.

    Each REAL variable has 3 integer unknowns (t, e, b exponents).
    Each constraint lhs == rhs yields 3 linear equations.

    Returns uniquely determined vars + free vars + conflicts.
    """
    from grounding.dimensions import Dimension

    DIMLESS = _get_dimensionless()

    # Gather all variable names
    vars_set: Set[str] = set()
    for c in constraints:
        vars_set |= set(c.lhs.coeffs.keys())
        vars_set |= set(c.rhs.coeffs.keys())
    vars_list = sorted(vars_set)
    n = len(vars_list)

    if n == 0:
        # No variables -- just check constant consistency
        conflicts = []
        for c in constraints:
            norm_const = c.lhs.const / c.rhs.const
            if norm_const != DIMLESS:
                conflicts.append((c.axiom,
                    f"Constant conflict at {c.path}: "
                    f"{c.lhs.const} != {c.rhs.const}"))
        return SolveResult(
            resolved={}, free_vars=set(),
            inconsistent=len(conflicts) > 0,
            conflicts=conflicts)

    idx = {v: i for i, v in enumerate(vars_list)}

    # Build augmented matrix [A | b_t, b_e, b_b]
    A: List[List[Fraction]] = []
    b_t: List[Fraction] = []
    b_e: List[Fraction] = []
    b_b: List[Fraction] = []
    sources: List[Constraint] = []

    for c in constraints:
        norm = c.lhs.sub(c.rhs)
        row = [Fraction(0)] * n
        for v, k in norm.coeffs.items():
            row[idx[v]] = Fraction(k)
        A.append(row)
        b_t.append(Fraction(-norm.const.time))
        b_e.append(Fraction(-norm.const.energy))
        b_b.append(Fraction(-norm.const.bits))
        sources.append(c)

    m = len(A)

    # RREF (Reduced Row Echelon Form)
    pivots: Dict[int, int] = {}
    r = 0
    for col in range(n):
        pivot = None
        for rr in range(r, m):
            if A[rr][col] != 0:
                pivot = rr
                break
        if pivot is None:
            continue

        if pivot != r:
            A[r], A[pivot] = A[pivot], A[r]
            b_t[r], b_t[pivot] = b_t[pivot], b_t[r]
            b_e[r], b_e[pivot] = b_e[pivot], b_e[r]
            b_b[r], b_b[pivot] = b_b[pivot], b_b[r]
            sources[r], sources[pivot] = sources[pivot], sources[r]

        piv = A[r][col]
        A[r] = [x / piv for x in A[r]]
        b_t[r] /= piv
        b_e[r] /= piv
        b_b[r] /= piv

        for rr in range(m):
            if rr == r:
                continue
            factor = A[rr][col]
            if factor == 0:
                continue
            A[rr] = [A[rr][j] - factor * A[r][j] for j in range(n)]
            b_t[rr] -= factor * b_t[r]
            b_e[rr] -= factor * b_e[r]
            b_b[rr] -= factor * b_b[r]

        pivots[r] = col
        r += 1
        if r == m:
            break

    # Check for inconsistency: 0x = nonzero
    conflicts = []
    for rr in range(m):
        if all(A[rr][j] == 0 for j in range(n)):
            if b_t[rr] != 0 or b_e[rr] != 0 or b_b[rr] != 0:
                c = sources[rr]
                conflicts.append((c.axiom,
                    f"Inconsistent at {c.path}: "
                    f"0 = ({b_t[rr]}, {b_e[rr]}, {b_b[rr]})"))

    if conflicts:
        return SolveResult(
            resolved={}, free_vars=set(vars_list),
            inconsistent=True, conflicts=conflicts)

    # Identify free columns (no pivot)
    pivot_cols = set(pivots.values())
    free_cols = [j for j in range(n) if j not in pivot_cols]
    free_vars = {vars_list[j] for j in free_cols}

    # Resolved: pivot var with no free-column dependencies
    resolved: Dict[str, Dimension] = {}
    for rr, pcol in pivots.items():
        depends_on_free = any(A[rr][j] != 0 for j in free_cols)
        if depends_on_free:
            free_vars.add(vars_list[pcol])
            continue
        t_val, e_val, b_val = b_t[rr], b_e[rr], b_b[rr]
        if (t_val.denominator != 1 or e_val.denominator != 1
                or b_val.denominator != 1):
            conflicts.append(("solver",
                f"Non-integer exponent for {vars_list[pcol]}"))
            free_vars.add(vars_list[pcol])
            continue
        resolved[vars_list[pcol]] = Dimension(
            int(t_val), int(e_val), int(b_val))

    return SolveResult(
        resolved=resolved, free_vars=free_vars,
        inconsistent=len(conflicts) > 0, conflicts=conflicts)
