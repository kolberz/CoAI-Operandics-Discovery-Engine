"""
grounding/dimensions.py

Physical dimensional analysis and the Landauer Bridge.
Implements SENTINEL Gate 3: Physical Units.

Corrections applied:
  Round 1: Constants now carry dimensions (LANDAUER = J/bit, etc.)
           times() is conservative: unknown * known = unknown
           Removed phantom 'landauer_energy' function symbol
  Round 2: LB2/LB3 reclassified as design assumptions (generated
           but clearly marked; causal.py handles classification)
  Round 3: DimensionalChecker tracks unknown_terms count so
           Sentinel can distinguish PASS from UNKNOWN
  Round 4: DimReport with PASS/FAIL/UNKNOWN verdict
           UNKNOWN treated as FAIL for deployment (no silent passes)
           Dimensioned zeros (ZERO_J, ZERO_bit, ZERO_s) in registry
  Round 5: v1.1 — Constraint-based inference for REAL variables
           Split unknowns into unknown_required / unknown_coverage
           Registry completeness (R_INF, R_PENALTY, sort-aware skips)
           Non-REAL sorts (MODULE, PRED, PROB) excluded from unknown counts
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from core.logic import (
    Term, Variable, Constant, Function, Formula,
    Equality, LessEq, Forall, Exists, Implies,
    And, Or, Not, Atom, MODULE, REAL
)
from grounding.dim_constraints import (
    alpha_rename, ConstraintCollector, solve_constraints,
    SolveResult,
)
import math


# ═══════════════════════════════════════════
# PHYSICAL CONSTANTS
# ═══════════════════════════════════════════

BOLTZMANN_K = 1.380649e-23       # J/K  (exact by 2019 SI redefinition)
ROOM_TEMP = 300.0                # K
LANDAUER_LIMIT = BOLTZMANN_K * ROOM_TEMP * math.log(2)  # ~2.85e-21 J/bit
FLOP_ENERGY_TYPICAL = 1e-11      # ~10 pJ per FLOP (modern GPU)

# Needed for sort comparisons — import or reconstruct PROB/PRED sorts
try:
    from core.logic import PROB, PRED
except ImportError:
    PROB = None
    PRED = None

# Sorts that are outside Gate 3's dimensional scope
_NON_NUMERIC_SORTS = set()
if MODULE is not None:
    _NON_NUMERIC_SORTS.add(MODULE)
if PROB is not None:
    _NON_NUMERIC_SORTS.add(PROB)
if PRED is not None:
    _NON_NUMERIC_SORTS.add(PRED)
# Also handle string-based sort matching as fallback
_NON_NUMERIC_SORT_NAMES = {"Module", "Predicate", "Probability", "Bool"}


def _is_non_numeric_sort(sort) -> bool:
    """Check if a sort is outside Gate 3 scope (MODULE/PRED/PROB/BOOL)."""
    if sort in _NON_NUMERIC_SORTS:
        return True
    # Fallback: string comparison
    return str(sort) in _NON_NUMERIC_SORT_NAMES


# ═══════════════════════════════════════════
# DIMENSION TYPE
# ═══════════════════════════════════════════

@dataclass(frozen=True)
class Dimension:
    """
    Physical dimension vector.
    Each field is an exponent of the corresponding base unit.

    Hash uses Morton-Z (bit-interleaved) encoding of the ℤ³
    exponent triple for O(1) locality-preserving lookups.
    (Quake-Style #11)
    """
    time: int = 0       # seconds
    energy: int = 0     # joules
    bits: int = 0       # information content

    @property
    def morton_key(self) -> int:
        """Morton-Z (bit-interleaved) key for the ℤ³ triple.

        Encodes signed ints via offset-binary (offset=128)
        then interleaves 8 bits from each axis into a 24-bit key.
        Bijective for exponents in [-128, 127].
        """
        offset = 128
        ut = self.time + offset
        ue = self.energy + offset
        ub = self.bits + offset
        key = 0
        for bit in range(8):
            key |= ((ut >> bit) & 1) << (3 * bit)
            key |= ((ue >> bit) & 1) << (3 * bit + 1)
            key |= ((ub >> bit) & 1) << (3 * bit + 2)
        return key

    def __hash__(self) -> int:
        return self.morton_key

    def __mul__(self, other: 'Dimension') -> 'Dimension':
        return Dimension(
            self.time + other.time,
            self.energy + other.energy,
            self.bits + other.bits,
        )

    def __truediv__(self, other: 'Dimension') -> 'Dimension':
        return Dimension(
            self.time - other.time,
            self.energy - other.energy,
            self.bits - other.bits,
        )

    def compatible(self, other: 'Dimension') -> bool:
        return self == other

    def __repr__(self):
        parts = []
        for name, exp in [("s", self.time), ("J", self.energy),
                          ("bit", self.bits)]:
            if exp == 1:
                parts.append(name)
            elif exp != 0:
                parts.append(f"{name}^{exp}")
        return ".".join(parts) if parts else "dimensionless"


# Standard dimension singletons
DIMENSIONLESS = Dimension()
TIME = Dimension(time=1)
ENERGY = Dimension(energy=1)
BITS = Dimension(bits=1)
ENERGY_PER_BIT = Dimension(energy=1, bits=-1)


# ═══════════════════════════════════════════
# DIMENSION REGISTRY
# ═══════════════════════════════════════════

class DimensionRegistry:
    """
    Maps function symbols and constant symbols to their
    physical dimensions.

    Two registries:
      output_dims  — for Function symbols (what dimension they return)
      const_dims   — for Constant symbols (what dimension they carry)

    A function with output_dims = None means "dimension depends
    on operands" (e.g., plus, max). These are resolved by
    DimensionalChecker._infer() contextually.
    """

    def __init__(self):
        self.output_dims: Dict[str, Optional[Dimension]] = {}
        self.const_dims: Dict[str, Optional[Dimension]] = {}
        self._init_standard()

    def _init_standard(self):
        # ── Function symbols: measured quantities ──
        self.output_dims["Risk"] = DIMENSIONLESS
        self.output_dims["ResourceCost"] = ENERGY
        self.output_dims["Comp"] = BITS
        self.output_dims["Ent"] = BITS
        self.output_dims["Dep"] = DIMENSIONLESS

        # ── Function symbols: arithmetic ──
        # These inherit/combine operand dimensions;
        # _infer handles them specially.
        for op in ("plus", "minus", "max", "min"):
            self.output_dims[op] = None
        self.output_dims["times"] = None
        self.output_dims["prob_weight"] = None

        # ── Function symbols: composition operators ──
        # These produce MODULE-typed terms, not measured quantities.
        # They don't have a physical dimension in the measurement sense.
        for op in ("Seq", "Par_Dyn", "Choice", "Barrier", "Sec_Filter"):
            self.output_dims[op] = None

        # ── Constant symbols ──
        self.const_dims["LANDAUER"] = ENERGY_PER_BIT   # kT·ln(2) J/bit
        self.const_dims["OVERHEAD"] = DIMENSIONLESS     # engineering ratio
        self.const_dims["R_ZERO"] = DIMENSIONLESS       # zero probability
        self.const_dims["DEP_ZERO"] = DIMENSIONLESS     # zero correlation

        # ── Dimensioned zeros ──
        self.const_dims["ZERO_J"] = ENERGY              # 0 joules
        self.const_dims["ZERO_bit"] = BITS              # 0 bits
        self.const_dims["ZERO_s"] = TIME                # 0 seconds
        self.const_dims["R_ONE"] = DIMENSIONLESS        # multiplicative 1
        self.const_dims["DEP_ONE"] = DIMENSIONLESS      # full dependence

        # ── Round 5: register remaining constants ──
        self.const_dims["R_INF"] = BITS                 # top of entropy lattice
        self.const_dims["R_PENALTY"] = DIMENSIONLESS    # risk penalty factor

    def get_dim(self, symbol: str) -> Optional[Dimension]:
        """Look up output dimension of a function symbol."""
        return self.output_dims.get(symbol)

    def get_const_dim(self, name: str) -> Optional[Dimension]:
        """Look up dimension of a constant symbol."""
        return self.const_dims.get(name)


# ═══════════════════════════════════════════
# CONSTRAINT SOLVER (Union-Find Propagation)
# ═══════════════════════════════════════════

class _DimNode:
    """Union-find node representing a dimension variable or concrete dim."""
    __slots__ = ('name', 'parent', 'rank', 'dim')

    def __init__(self, name: str, dim: Optional[Dimension] = None):
        self.name = name
        self.parent = self
        self.rank = 0
        self.dim = dim


class DimConstraintSolver:
    """
    DEPRECATED: Legacy union-find solver; retained for reference;
    not used in Gate 3 v1.2 pipeline.

    Collects dimensional constraints from the axiom AST and solves
    them via union-find propagation.

    Supports:
      - Equality constraints: dim(a) = dim(b)
      - Concrete assignments: dim(a) = ENERGY
      - Additive constraints: dim(plus(a,b)) = dim(a) = dim(b)

    Does NOT handle multiplication constraints (would require
    linear integer solver over exponents). Times() results remain
    unknown unless both operand dims are concrete.
    """

    def __init__(self, registry: DimensionRegistry):
        self.registry = registry
        self._nodes: Dict[str, _DimNode] = {}
        self._conflicts: List[Tuple[str, Dimension, Dimension]] = []

    def _get_node(self, key: str,
                  dim: Optional[Dimension] = None) -> _DimNode:
        if key not in self._nodes:
            self._nodes[key] = _DimNode(key, dim)
        node = self._nodes[key]
        # If we have a concrete dim and the node doesn't, set it
        if dim is not None and node.dim is None:
            node.dim = dim
        return node

    def _find(self, node: _DimNode) -> _DimNode:
        """Find root with path compression."""
        while node.parent is not node:
            node.parent = node.parent.parent
            node = node.parent
        return node

    def _unify(self, a: _DimNode, b: _DimNode, context: str = ""):
        """Unify two dimension nodes. Detects conflicts."""
        ra = self._find(a)
        rb = self._find(b)
        if ra is rb:
            return

        # Check for conflicts
        if (ra.dim is not None and rb.dim is not None
                and ra.dim != rb.dim):
            self._conflicts.append((context, ra.dim, rb.dim))
            return

        # Merge by rank; preserve the node with a concrete dim
        if ra.rank < rb.rank:
            ra, rb = rb, ra
        rb.parent = ra
        if ra.rank == rb.rank:
            ra.rank += 1
        # Propagate concrete dim
        if ra.dim is None:
            ra.dim = rb.dim

    def collect_from_axioms(self, axioms: List[Formula],
                            names: List[str]):
        """Walk all axioms and collect constraints."""
        for axiom, name in zip(axioms, names):
            self._collect_formula(axiom, name)

    def _collect_formula(self, f: Formula, axiom: str):
        """Recursively collect constraints from a formula."""
        if isinstance(f, (Equality, LessEq)):
            lk = self._collect_term(f.left, axiom)
            rk = self._collect_term(f.right, axiom)
            if lk is not None and rk is not None:
                self._unify(
                    self._get_node(lk),
                    self._get_node(rk),
                    context=axiom,
                )

        elif isinstance(f, (Forall, Exists)):
            self._collect_formula(f.body, axiom)

        elif isinstance(f, Implies):
            self._collect_formula(f.antecedent, axiom)
            self._collect_formula(f.consequent, axiom)

        elif isinstance(f, (And, Or)):
            self._collect_formula(f.left, axiom)
            self._collect_formula(f.right, axiom)

        elif isinstance(f, Not):
            self._collect_formula(f.formula, axiom)

        elif isinstance(f, Atom):
            for a in f.args:
                self._collect_term(a, axiom)

    def _collect_term(self, t: Term, axiom: str) -> Optional[str]:
        """
        Walk a term, create dim-nodes, and collect constraints.
        Returns a string key for this term's dim-node, or None
        if the term is outside dimensional scope.

        Variables are scoped per-axiom (key = var:{axiom}:{name})
        because universally-quantified REAL vars like R1 in
        'Forall R1. plus(R1, R_ZERO) = R1' are polymorphic:
        they must work for ANY dimension. Giving them a single
        global dim-var would create false constraint conflicts.
        Constants remain global (they have fixed dimensions).
        """
        if isinstance(t, Variable):
            if _is_non_numeric_sort(t.sort):
                return None  # MODULE/PRED/PROB: outside scope
            key = f"var:{axiom}:{t.name}"
            self._get_node(key)
            return key

        if isinstance(t, Constant):
            if _is_non_numeric_sort(t.sort):
                return None
            key = f"const:{t.name}"
            dim = self.registry.get_const_dim(t.name)
            self._get_node(key, dim)
            return key

        if isinstance(t, Function):
            # Measured functions: known output dim
            known = self.registry.get_dim(t.symbol)
            if known is not None:
                key = f"func:{t.symbol}:{id(t)}"
                self._get_node(key, known)
                # Recurse into args for variable coverage,
                # but don't constrain args (they're MODULE-typed)
                for a in t.args:
                    self._collect_term(a, axiom)
                return key

            # Additive: all args must have same dim
            if t.symbol in ("plus", "minus", "max", "min"):
                key = f"add:{t.symbol}:{id(t)}"
                self._get_node(key)
                for a in t.args:
                    ak = self._collect_term(a, axiom)
                    if ak is not None:
                        self._unify(
                            self._get_node(key),
                            self._get_node(ak),
                            context=f"{axiom}:{t.symbol}",
                        )
                return key

            # Multiplication: can't unify, but still recurse
            if t.symbol == "times":
                for a in t.args:
                    self._collect_term(a, axiom)
                # Can't express dim(a)*dim(b) in union-find,
                # but if both args are concrete after solving,
                # _infer() will handle them.
                return None  # no single key for product dim

            # prob_weight: inherits from second arg
            if t.symbol == "prob_weight":
                args_keys = []
                for a in t.args:
                    args_keys.append(self._collect_term(a, axiom))
                if len(args_keys) >= 2 and args_keys[1] is not None:
                    return args_keys[1]
                return None

            # Composition operators: MODULE scope
            if t.symbol in ("Seq", "Par_Dyn", "Choice",
                            "Barrier", "Sec_Filter"):
                for a in t.args:
                    self._collect_term(a, axiom)
                return None

            # Unknown function: recurse
            for a in t.args:
                self._collect_term(a, axiom)
            return None

        return None

    def solve(self) -> Dict[str, Dimension]:
        """
        After collecting constraints, resolve all dimension variables.

        Variables are scoped per-axiom (key = var:{axiom}:{name}).
        We consolidate: a variable gets an inferred dim only if ALL
        axiom-scoped instances that resolved agree on the same dim.
        If they disagree, we leave the variable as unknown (it's
        polymorphic and can't be assigned a single dim).

        Returns a map from variable name to inferred Dimension.
        """
        # Collect per-variable: {varname: set of inferred dims}
        per_var: Dict[str, Set[Dimension]] = {}
        for key, node in self._nodes.items():
            root = self._find(node)
            if key.startswith("var:") and root.dim is not None:
                # key = "var:{axiom}:{varname}"
                parts = key.split(":", 2)
                if len(parts) == 3:
                    varname = parts[2]
                else:
                    varname = parts[1]
                if varname not in per_var:
                    per_var[varname] = set()
                per_var[varname].add(root.dim)

        # Only report if all instances agree on one dim
        result: Dict[str, Dimension] = {}
        for varname, dims in per_var.items():
            if len(dims) == 1:
                result[varname] = next(iter(dims))
            # else: polymorphic / disagreement → leave unknown
        return result

    def same_group(self, key_a: str, key_b: str) -> bool:
        """Check if two keys belong to the same constraint group."""
        na = self._nodes.get(key_a)
        nb = self._nodes.get(key_b)
        if na is None or nb is None:
            return False
        return self._find(na) is self._find(nb)

    def term_key(self, term: Term, axiom: str) -> Optional[str]:
        """Get the constraint key for a term (without creating new nodes)."""
        if isinstance(term, Variable):
            if _is_non_numeric_sort(term.sort):
                return None
            key = f"var:{axiom}:{term.name}"
            return key if key in self._nodes else None
        if isinstance(term, Constant):
            if _is_non_numeric_sort(term.sort):
                return None
            key = f"const:{term.name}"
            return key if key in self._nodes else None
        if isinstance(term, Function):
            known = self.registry.get_dim(term.symbol)
            if known is not None:
                key = f"func:{term.symbol}:{id(term)}"
                return key if key in self._nodes else None
            # For additive ops, the key was created in _collect_term
            if term.symbol in ("plus", "minus", "max", "min"):
                key = f"add:{term.symbol}:{id(term)}"
                return key if key in self._nodes else None
        return None

    def resolve_var_in_axiom(self, varname: str,
                             axiom: str) -> Optional[Dimension]:
        """Resolve a variable's dimension within a specific axiom's scope.

        This handles polymorphic variables (e.g., R1 in generic
        arithmetic axioms) by looking up the per-axiom constraint
        node rather than the globally consolidated result.
        """
        key = f"var:{axiom}:{varname}"
        node = self._nodes.get(key)
        if node is None:
            return None
        root = self._find(node)
        return root.dim

    @property
    def conflicts(self) -> List[Tuple[str, Dimension, Dimension]]:
        return self._conflicts


# ═══════════════════════════════════════════
# DIMENSIONAL CHECKER
# ═══════════════════════════════════════════

@dataclass
class DimError:
    axiom_name: str
    formula_str: str
    message: str
    path: str = ""
    left_dim: Optional[Dimension] = None
    right_dim: Optional[Dimension] = None


# ── Checker feature flags (auto-generated calibration markers) ──
# Adding/removing/toggling a feature constitutes an instrument
# recalibration and changes checker_version automatically.
CHECKER_FEATURES = {
    "traverse_atoms": True,
    "count_real_vars": True,
    "mixed_unit_additive_is_error": True,
    "constraint_solver_gaussian": True,
    "alpha_renaming": True,
    "multiplicative_inference": True,
    "obligation_reclassification": True,
    "sort_aware_skip": True,
    "dimensioned_zeros": True,
    "landauer_bridge": True,
}
_CHECKER_SEMANTIC_VERSION = "1.2.0"

import hashlib as _hashlib


def _compute_checker_version() -> str:
    """Deterministic version hash from features + semantic version."""
    features_str = str(sorted(CHECKER_FEATURES.items()))
    payload = f"{_CHECKER_SEMANTIC_VERSION}:{features_str}"
    return _hashlib.sha256(payload.encode()).hexdigest()[:12]


def _compute_calibration_markers() -> List[str]:
    """Active feature flags as calibration markers."""
    return sorted(k for k, v in CHECKER_FEATURES.items() if v)


CHECKER_VERSION = _compute_checker_version()
CALIBRATION_MARKERS = _compute_calibration_markers()


@dataclass
class DimReport:
    """Gate 3 report with mandatory PASS/FAIL/UNKNOWN verdict.

    Verdict contract (v1.1):
      - errors > 0                              -> FAIL
      - errors == 0 and unknown_required > 0    -> UNKNOWN (blocks deployment)
      - errors == 0 and unknown_required == 0   -> PASS

    unknown_coverage terms are outside any dimensional obligation;
    they are reported as warnings but do not block deployment.

    Metrology discipline:
      - checker_version:     deterministic hash of feature flags + semver
      - calibration_markers: active feature flags (auto-generated, no manual drift)
    """
    checked: int
    errors: List[DimError]
    warnings: List[str]
    unknown_required: int
    unknown_coverage: int
    unknown_constants: FrozenSet[str]
    unknown_functions: FrozenSet[str]
    inferred_dims: Dict[str, Dimension]
    coverage_sample: List[str] = field(default_factory=list)
    checker_version: str = ""
    calibration_markers: List[str] = field(default_factory=list)

    @property
    def unknown_terms(self) -> int:
        """Total unknowns (for backward compat and reporting)."""
        return self.unknown_required + self.unknown_coverage

    @property
    def verdict(self) -> str:
        if self.errors:
            return "FAIL"
        if self.unknown_required > 0:
            return "UNKNOWN"
        return "PASS"

    @property
    def passes_deployment(self) -> bool:
        return self.verdict == "PASS"


class DimensionalChecker:
    """
    Two-pass static analyzer for dimensional consistency.

    Pass 1 — Constraint collection + solve:
      Walk all axioms, generate equality constraints on dimension
      variables, solve via union-find to infer REAL variable dims.

    Pass 2 — Check + classify:
      Walk all axioms with resolved dims, check each Equality/LessEq
      for compatibility, classify remaining unknowns as "required"
      (blocks a dimensional obligation) or "coverage" (doesn't).

    Tracks:
      errors              — provably incompatible dimensions (FAIL)
      warnings            — suspicious but not provably wrong
      unknown_required    — blocks deployment (in obligation context)
      unknown_coverage    — does not block deployment (warning only)
      unknown_constants   — constant names not in registry
      unknown_functions   — function symbols not in registry
    """

    def __init__(self, registry: DimensionRegistry = None):
        self.registry = registry or DimensionRegistry()
        self.errors: List[DimError] = []
        self.warnings: List[str] = []
        self.checked: int = 0
        self.unknown_required: int = 0
        self.unknown_coverage: int = 0
        self._coverage_vars: Set[str] = set()
        self.unknown_constants: Set[str] = set()
        self.unknown_functions: Set[str] = set()
        self._inferred_dims: Dict[str, Dimension] = {}

    def check_axiom_set(self, axioms: List[Formula],
                        names: List[str] = None) -> DimReport:
        """Check all axioms. Returns a DimReport with verdict.

        Architecture (Round 3):
          1. alpha-rename bound variables per axiom
          2. Collect linear constraints (incl. times/divide)
          3. Solve via Gaussian elimination over Q
          4. Walk axioms with resolved dims, classify unknowns
        """
        self.errors = []
        self.warnings = []
        self.checked = 0
        self.unknown_required = 0
        self.unknown_coverage = 0
        self.unknown_constants = set()
        self.unknown_functions = set()

        if names is None:
            names = [f"axiom_{i}" for i in range(len(axioms))]

        # ── Step 1: Alpha-rename bound variables per axiom ──
        renamed = [
            alpha_rename(ax, name)
            for ax, name in zip(axioms, names)
        ]

        # ── Step 2: Collect constraints (incl. times/divide) ──
        collector = ConstraintCollector(self.registry)
        for ax, name in zip(renamed, names):
            collector.collect_formula(ax, name, name)

        self.unknown_constants = set(collector.unknown_constants)
        if collector.unhandled_terms:
            for t in sorted(collector.unhandled_terms):
                self.warnings.append(
                    f"Unhandled term in constraint collection: {t}")

        # ── Step 3: Solve via Gaussian elimination ──
        self._solve_result: SolveResult = solve_constraints(
            collector.constraints)
        self._inferred_dims = dict(self._solve_result.resolved)

        # Solver conflicts become errors
        for axiom_name, reason in self._solve_result.conflicts:
            self.errors.append(DimError(
                axiom_name=axiom_name,
                formula_str="constraint conflict",
                message=f"Constraint solver: {reason}",
            ))

        # ── Step 4: Walk (renamed) axioms, check + classify ──
        for axiom, name in zip(renamed, names):
            self.checked += 1
            self._current_axiom = name
            self._check_formula(axiom, name)

        # Canonical error ordering for determinism (CI-safe)
        sorted_errors = sorted(
            self.errors,
            key=lambda e: (e.axiom_name, e.path, e.message))

        return DimReport(
            checked=len(axioms),
            errors=self.errors,
            warnings=self.warnings,
            unknown_required=self.unknown_required,
            unknown_coverage=self.unknown_coverage,
            unknown_constants=frozenset(self.unknown_constants),
            unknown_functions=frozenset(self.unknown_functions),
            inferred_dims=self._inferred_dims,
            coverage_sample=sorted(list(self._coverage_vars))[:5],
            checker_version=CHECKER_VERSION,
            calibration_markers=CALIBRATION_MARKERS,
        )

    def _check_obligation(self, left_term: Term, right_term: Term,
                          name: str, kind: str,
                          formula: Formula):
        """Check a dimensional obligation (Equality or LessEq).

        Classification (v1.2, Gaussian solver):
          - Both dims known and incompatible  -> ERROR
          - Both dims known and compatible    -> OK
          - One known, one None               -> unknown_required
          - Both None, all vars are free      -> unknown_coverage
            (solver found no conflicting constraints)
          - Both None, mixed free/unseen      -> unknown_required
        """
        req_before = self.unknown_required
        cov_before = self.unknown_coverage

        ld = self._infer(left_term, name, f"{kind}.left",
                         in_obligation=True)
        rd = self._infer(right_term, name, f"{kind}.right",
                         in_obligation=True)

        if ld is not None and rd is not None:
            if not ld.compatible(rd):
                self.errors.append(DimError(
                    axiom_name=name,
                    formula_str=str(formula)[:80],
                    message=f"{kind} compares {ld} with {rd}",
                    left_dim=ld, right_dim=rd,
                ))
        elif ld is None and rd is None:
            # Both unknown. Check if all involved vars are in the
            # solver's variable set (meaning they participated in
            # constraints and are internally consistent).
            involved = self._collect_real_var_names(left_term) | \
                       self._collect_real_var_names(right_term)
            if (involved
                    and involved <= self._solve_result.all_vars):
                # All vars known to solver (free or resolved)
                # -> reclassify unknowns as coverage
                new_req = self.unknown_required - req_before
                if new_req > 0:
                    self.unknown_required -= new_req
                    self.unknown_coverage += new_req
                    self._coverage_vars.update(involved)
        # If exactly one is None: stays as unknown_required

    def _collect_real_var_names(self, term: Term) -> Set[str]:
        """Collect all REAL (numeric) variable names in a term tree."""
        result: Set[str] = set()
        if isinstance(term, Variable):
            if not _is_non_numeric_sort(term.sort):
                result.add(term.name)
        elif isinstance(term, Function):
            for a in term.args:
                result |= self._collect_real_var_names(a)
        return result

    def _check_formula(self, formula: Formula, name: str):
        """Recursively check a formula for dimensional consistency."""
        if isinstance(formula, Equality):
            self._check_obligation(
                formula.left, formula.right, name, "eq", formula)

        elif isinstance(formula, LessEq):
            self._check_obligation(
                formula.left, formula.right, name, "leq", formula)

        elif isinstance(formula, (Forall, Exists)):
            self._check_formula(formula.body, name)

        elif isinstance(formula, Implies):
            self._check_formula(formula.antecedent, name)
            self._check_formula(formula.consequent, name)

        elif isinstance(formula, (And, Or)):
            self._check_formula(formula.left, name)
            self._check_formula(formula.right, name)

        elif isinstance(formula, Not):
            self._check_formula(formula.formula, name)

        elif isinstance(formula, Atom):
            for i, t in enumerate(formula.args):
                self._infer(t, name, f"atom.{formula.predicate}[{i}]",
                            in_obligation=False)

    def _infer(self, term: Term,
               axiom: str = "", path: str = "",
               in_obligation: bool = False) -> Optional[Dimension]:
        """
        Infer physical dimension of a term.

        Returns None when dimension cannot be determined.
        Classifies unknowns as required vs coverage based on
        whether we're inside a dimensional obligation context
        (Equality, LessEq, additive op).

        Non-numeric sorts (MODULE, PRED, PROB) return None
        without incrementing any unknown counter.

        Args:
            term:           the AST node to infer
            axiom:          name of the enclosing axiom
            path:           dotted path inside the axiom
            in_obligation:  True if this term is part of a
                           dimensional check (=, ≤, plus, max)
        """
        if isinstance(term, Variable):
            # Non-numeric sorts: outside Gate 3 scope
            if _is_non_numeric_sort(term.sort):
                return None  # not counted as unknown

            # Check if Gaussian solver resolved this variable.
            # After alpha-renaming, each axiom's bound vars have
            # unique names, so global lookup is correct.
            inferred = self._inferred_dims.get(term.name)
            if inferred is not None:
                return inferred

            # Genuinely unknown REAL variable
            if in_obligation:
                self.unknown_required += 1
            else:
                self.unknown_coverage += 1
            return None

        if isinstance(term, Constant):
            # Non-numeric sorts: outside Gate 3 scope
            if _is_non_numeric_sort(term.sort):
                return None

            dim = self.registry.get_const_dim(term.name)
            if dim is None:
                self.unknown_constants.add(term.name)
                if in_obligation:
                    self.unknown_required += 1
                else:
                    self.unknown_coverage += 1
            return dim

        if isinstance(term, Function):
            # Direct lookup for measured quantities
            known = self.registry.get_dim(term.symbol)
            if known is not None:
                return known

            # ── Additive operators: operands MUST match ──
            if term.symbol in ("plus", "minus", "max", "min"):
                arg_dims = [
                    self._infer(a, axiom,
                                f"{path}.{term.symbol}[{i}]",
                                in_obligation=True)
                    for i, a in enumerate(term.args)
                ]
                known_dims = [d for d in arg_dims if d is not None]
                if len(known_dims) >= 2:
                    first = known_dims[0]
                    for d in known_dims[1:]:
                        if not first.compatible(d):
                            self.errors.append(DimError(
                                axiom_name=axiom,
                                formula_str=(
                                    f"{term.symbol} at {path}"),
                                message=(
                                    f"{term.symbol} mixes "
                                    f"{first} and {d}"),
                                left_dim=first, right_dim=d,
                            ))
                            return None  # poisoned
                    return first
                elif len(known_dims) == 1:
                    return known_dims[0]
                # All args unknown
                if in_obligation:
                    self.unknown_required += 1
                else:
                    self.unknown_coverage += 1
                return None

            # ── Multiplication: conservative ──
            if term.symbol == "times":
                if len(term.args) != 2:
                    return None
                d0 = self._infer(term.args[0], axiom,
                                 f"{path}.times[0]",
                                 in_obligation=in_obligation)
                d1 = self._infer(term.args[1], axiom,
                                 f"{path}.times[1]",
                                 in_obligation=in_obligation)
                if d0 is not None and d1 is not None:
                    return d0 * d1
                # Partial unknown: cannot infer product
                if in_obligation:
                    self.unknown_required += 1
                else:
                    self.unknown_coverage += 1
                return None

            # ── Division: divide dims ──
            if term.symbol == "divide":
                if len(term.args) != 2:
                    return None
                d0 = self._infer(term.args[0], axiom,
                                 f"{path}.divide[0]",
                                 in_obligation=in_obligation)
                d1 = self._infer(term.args[1], axiom,
                                 f"{path}.divide[1]",
                                 in_obligation=in_obligation)
                if d0 is not None and d1 is not None:
                    return d0 / d1
                if in_obligation:
                    self.unknown_required += 1
                else:
                    self.unknown_coverage += 1
                return None

            # ── Probability weighting: inherits from second arg ──
            if term.symbol == "prob_weight":
                if len(term.args) >= 2:
                    return self._infer(term.args[1], axiom,
                                       f"{path}.prob_weight[1]",
                                       in_obligation=in_obligation)
                if in_obligation:
                    self.unknown_required += 1
                else:
                    self.unknown_coverage += 1
                return None

            # ── Composition operators produce MODULE, not a measure ──
            if term.symbol in ("Seq", "Par_Dyn", "Choice",
                               "Barrier", "Sec_Filter"):
                return None  # not measured directly; not unknown

            # Unknown function symbol
            self.unknown_functions.add(term.symbol)
            if in_obligation:
                self.unknown_required += 1
            else:
                self.unknown_coverage += 1
            return None

        # Fallback: unknown term type
        if in_obligation:
            self.unknown_required += 1
        else:
            self.unknown_coverage += 1
            self._coverage_vars.add(term.name)
        return None


# ═══════════════════════════════════════════
# LANDAUER BRIDGE
# ═══════════════════════════════════════════

class LandauerBridge:
    """
    Conversion between BITS and ENERGY domains.

    Physical law (Landauer, 1961):
      Erasing 1 bit of information in a system at temperature T
      dissipates at least kT·ln(2) joules.

    This provides EXACTLY ONE universally valid bridge:
      ResourceCost(M) >= Comp(M) · LANDAUER          [LB1: lower bound]

    Additional bridge axioms (LB2, LB3) are generated but clearly
    marked as DESIGN ASSUMPTIONS, not physical laws. Their validity
    depends on engineering context (overhead budget, scheduling
    model, etc.) and must be tracked in the causal graph (Gate 5).
    """

    def __init__(self, temperature: float = ROOM_TEMP):
        self.temperature = temperature
        self.landauer_factor = BOLTZMANN_K * temperature * math.log(2)

    def bits_to_joules(self, bits: float) -> float:
        """Minimum energy to erase given number of bits."""
        return bits * self.landauer_factor

    def joules_to_bits(self, joules: float) -> float:
        """Maximum bits erasable with given energy."""
        return joules / self.landauer_factor

    def generate_bridge_axioms(self) -> List[Tuple[Formula, str, str]]:
        """
        Generate axioms bridging BITS and ENERGY domains.

        Returns list of (formula, name, classification) triples.
        classification is one of:
          "physical_law"         — universally valid
          "design_assumption"    — valid only under stated conditions

        The dimensional checker can now verify all three:
          Comp(M)   -> BITS
          LANDAUER  -> ENERGY_PER_BIT  (J/bit)
          times(Comp(M), LANDAUER) -> BITS * J/bit = ENERGY  ✓
          ResourceCost(M) -> ENERGY
          ENERGY compatible ENERGY  ✓  Gate 3 passes
        """
        m1 = Variable("M1", MODULE)
        m2 = Variable("M2", MODULE)
        landauer = Constant("LANDAUER", REAL)
        overhead = Constant("OVERHEAD", REAL)
        R_ZERO = Constant("R_ZERO", REAL)
        DEP_ZERO = Constant("DEP_ZERO", REAL)

        def Comp(m):
            return Function("Comp", (m,), REAL)

        def Cost(m):
            return Function("ResourceCost", (m,), REAL)

        def Risk(m):
            return Function("Risk", (m,), REAL)

        def Dep(a, b):
            return Function("Dep", (a, b), REAL)

        def times(a, b):
            return Function("times", (a, b), REAL)

        axioms = []

        # ── LB1: Landauer Lower Bound ────────────
        axioms.append((
            Forall(m1, LessEq(
                times(Comp(m1), landauer),
                Cost(m1),
            )),
            "landauer_lower_bound",
            "physical_law",
        ))

        # ── LB2: Cost Upper Bound (design assumption) ────
        axioms.append((
            Forall(m1, Implies(
                Equality(Risk(m1), R_ZERO),
                LessEq(
                    Cost(m1),
                    times(times(Comp(m1), landauer), overhead),
                ),
            )),
            "cost_upper_bound",
            "design_assumption",
        ))

        # ── LB3: Parallel Cost Lower Bound (design assumption) ──
        axioms.append((
            Forall(m1, Forall(m2, Implies(
                Equality(Dep(m1, m2), DEP_ZERO),
                LessEq(
                    times(
                        Function("max", (Comp(m1), Comp(m2)), REAL),
                        landauer,
                    ),
                    Cost(Function("Par_Dyn", (m1, m2), MODULE)),
                ),
            ))),
            "parallel_cost_lower_bound",
            "design_assumption",
        ))

        return axioms

    def report(self) -> str:
        lines = [
            "Landauer Bridge Configuration",
            f"  Temperature:     {self.temperature} K",
            f"  Landauer limit:  {self.landauer_factor:.3e} J/bit",
            f"  Practical FLOP:  {FLOP_ENERGY_TYPICAL:.3e} J/FLOP",
            f"  Efficiency gap:  "
            f"{FLOP_ENERGY_TYPICAL / self.landauer_factor:.0f}x "
            f"above Landauer",
        ]
        return "\n".join(lines)
