"""
tests/test_dim_constraints.py

Acceptance tests for the Round 3 constraint-based dimensional
inference engine. Tests cover:

  A) Multiplicative inference (times/divide)
  B) Inequality inference (LessEq)
  C) Conflicting transitive constraints
  D) Alpha-rename isolation
  E) Idempotency
  F) Full pipeline regression
"""

import pytest
from core.logic import (
    Variable, Constant, Function, Equality, LessEq,
    Forall, Implies, MODULE, REAL,
)
from grounding.dimensions import (
    Dimension, DimensionRegistry, DimensionalChecker,
    DIMENSIONLESS, BITS, ENERGY, ENERGY_PER_BIT,
)
from grounding.dim_constraints import (
    alpha_rename, ConstraintCollector, solve_constraints,
    DimExpr,
)


# ── Helpers ──

M = MODULE
R = REAL

def var(name, sort=R):
    return Variable(name=name, sort=sort)

def const(name, sort=R):
    return Constant(name=name, sort=sort)

def func(symbol, *args, sort=R):
    return Function(symbol=symbol, args=tuple(args), sort=sort)

def mod_var(name):
    return Variable(name=name, sort=M)

def mod_func(symbol, *args):
    return Function(symbol=symbol, args=tuple(args), sort=M)


# =============================================
# A) MULTIPLICATIVE INFERENCE
# =============================================

class TestMultiplicativeInference:
    """Test that times/divide produce correct dimensional constraints."""

    def test_times_comp_landauer_equals_energy(self):
        """Forall M. ResourceCost(M) <= times(Comp(M), LANDAUER)
        Should infer: dim(times(Comp(M), LANDAUER)) = bit * J/bit = J
        And: ResourceCost(M) = J
        So the obligation is dimensionally consistent.
        """
        m1 = mod_var("M1")
        axiom = Forall(
            variable=m1,
            body=LessEq(
                left=func("ResourceCost", m1),
                right=func("times",
                           func("Comp", m1),
                           const("LANDAUER")),
            ),
        )
        checker = DimensionalChecker()
        report = checker.check_axiom_set([axiom], ["landauer_bridge"])
        assert report.errors == [], f"Expected no errors: {report.errors}"
        assert report.verdict == "PASS"

    def test_times_infers_variable_dim(self):
        """times(x, LANDAUER) = ResourceCost(M)
        => x + J/bit = J => x = bit
        """
        x = var("x")
        m1 = mod_var("M1")
        axiom = Forall(
            variable=m1,
            body=Equality(
                left=func("times", x, const("LANDAUER")),
                right=func("ResourceCost", m1),
            ),
        )
        registry = DimensionRegistry()
        renamed = alpha_rename(axiom, "test")
        collector = ConstraintCollector(registry)
        collector.collect_formula(renamed, "test", "root")
        result = solve_constraints(collector.constraints)

        # x should be resolved to BITS
        x_resolved = None
        for name, dim in result.resolved.items():
            if name.startswith("x") or name == "x":
                x_resolved = dim
                break
        # x is a free variable (not bound by Forall), so it keeps
        # its original name
        assert result.resolved.get("x") == BITS, \
            f"Expected x=BITS, got {result.resolved}"

    def test_divide_inference(self):
        """divide(ResourceCost(M), Comp(M)) should have dim J/bit."""
        m1 = mod_var("M1")
        axiom = Forall(
            variable=m1,
            body=Equality(
                left=func("divide",
                           func("ResourceCost", m1),
                           func("Comp", m1)),
                right=const("LANDAUER"),
            ),
        )
        checker = DimensionalChecker()
        report = checker.check_axiom_set([axiom], ["divide_test"])
        assert report.errors == [], f"Expected no errors: {report.errors}"
        assert report.verdict == "PASS"

    def test_reverse_multiplicative_inference(self):
        """times(Comp(M), LANDAUER) = y => y = ENERGY"""
        y = var("y")
        m1 = mod_var("M1")
        axiom = Forall(
            variable=m1,
            body=Equality(
                left=func("times",
                          func("Comp", m1),
                          const("LANDAUER")),
                right=y,
            ),
        )
        registry = DimensionRegistry()
        renamed = alpha_rename(axiom, "test")
        collector = ConstraintCollector(registry)
        collector.collect_formula(renamed, "test", "root")
        result = solve_constraints(collector.constraints)
        
        y_resolved = result.resolved.get("y")
        assert y_resolved == ENERGY, \
            f"Expected y=ENERGY, got {y_resolved}"


# =============================================
# B) INEQUALITY INFERENCE
# =============================================

class TestInequalityInference:
    """Test that LessEq generates dimensional constraints."""

    def test_lesseq_consistent(self):
        """x <= ResourceCost(M) should infer dim(x) = ENERGY."""
        x = var("x")
        m1 = mod_var("M1")
        axiom = Forall(
            variable=m1,
            body=LessEq(
                left=x,
                right=func("ResourceCost", m1),
            ),
        )
        registry = DimensionRegistry()
        renamed = alpha_rename(axiom, "test")
        collector = ConstraintCollector(registry)
        collector.collect_formula(renamed, "test", "root")
        result = solve_constraints(collector.constraints)
        assert result.resolved.get("x") == ENERGY, \
            f"Expected x=ENERGY, got {result.resolved}"

    def test_lesseq_incompatible(self):
        """Comp(M) <= ResourceCost(M) should produce an error
        (BITS != ENERGY)."""
        m1 = mod_var("M1")
        axiom = Forall(
            variable=m1,
            body=LessEq(
                left=func("Comp", m1),
                right=func("ResourceCost", m1),
            ),
        )
        checker = DimensionalChecker()
        report = checker.check_axiom_set([axiom], ["incompatible"])
        assert len(report.errors) > 0, "Expected dimensional error"
        assert report.verdict == "FAIL"


# =============================================
# C) CONFLICTING TRANSITIVE CONSTRAINTS
# =============================================

class TestConflictingConstraints:
    """Test that conflicting constraints are detected."""

    def test_transitive_conflict(self):
        """x = ResourceCost(M) AND x = Comp(M) should conflict
        (ENERGY != BITS via transitivity)."""
        x = var("x")
        m1 = mod_var("M1")
        axiom1 = Equality(
            left=x,
            right=func("ResourceCost", m1),
        )
        axiom2 = Equality(
            left=x,
            right=func("Comp", m1),
        )
        checker = DimensionalChecker()
        report = checker.check_axiom_set(
            [axiom1, axiom2],
            ["conflict_a", "conflict_b"],
        )
        # Should produce either solver conflict or _infer error
        assert report.verdict == "FAIL", \
            f"Expected FAIL, got {report.verdict}"

    def test_additive_compatibility_enforcement(self):
        """plus(ResourceCost(M), Comp(M)) = z must FAIL
        because ENERGY != BITS."""
        z = var("z")
        m1 = mod_var("M1")
        axiom = Forall(
            variable=m1,
            body=Equality(
                left=func("plus",
                          func("ResourceCost", m1),
                          func("Comp", m1)),
                right=z,
            ),
        )
        checker = DimensionalChecker()
        report = checker.check_axiom_set([axiom], ["additive_fail"])
        assert report.verdict == "FAIL", \
            f"Expected FAIL due to additive mismatch, got {report.verdict}"
        assert len(report.errors) > 0


# =============================================
# D) ALPHA-RENAME ISOLATION
# =============================================

class TestAlphaRename:
    """Test that bound variables in different axioms don't unify."""

    def test_same_name_different_axioms(self):
        """R1 in axiom_7: plus(R1, R_ZERO) = R1  -> R1: DIMENSIONLESS
           R1 in axiom_26: min(R1, R_INF) = R1   -> R1: BITS
           These should NOT conflict because alpha-renaming
           gives them different names."""
        r1 = var("R1")
        axiom_7 = Forall(
            variable=r1,
            body=Equality(
                left=func("plus", r1, const("R_ZERO")),
                right=r1,
            ),
        )
        axiom_26 = Forall(
            variable=r1,
            body=Equality(
                left=func("min", r1, const("R_INF")),
                right=r1,
            ),
        )
        checker = DimensionalChecker()
        report = checker.check_axiom_set(
            [axiom_7, axiom_26],
            ["additive_identity", "min_identity"],
        )
        # Should PASS: alpha-renaming isolates R1 in each axiom
        assert report.errors == [], \
            f"Expected no errors (alpha isolation): {report.errors}"
        assert report.verdict == "PASS"

    def test_alpha_rename_produces_unique_names(self):
        """The renamed variables should have unique names."""
        r1 = var("R1")
        formula = Forall(variable=r1, body=Equality(left=r1, right=r1))
        f1 = alpha_rename(formula, "axiom_A")
        f2 = alpha_rename(formula, "axiom_B")
        # The bound variable names should differ
        assert f1.variable.name != f2.variable.name, \
            "Alpha-renamed vars should have distinct names"
        assert "@axiom_A#" in f1.variable.name
        assert "@axiom_B#" in f2.variable.name


# =============================================
# E) IDEMPOTENCY
# =============================================

class TestIdempotency:
    """Two runs with same input produce identical reports."""

    def test_idempotent_reports(self):
        """Running check_axiom_set twice on the same axioms
        must yield identical DimReports."""
        from discovery.engine import CoAIOperandicsExplorer
        explorer = CoAIOperandicsExplorer(
            max_clauses=100, max_depth=3,
            min_interestingness=0.1)

        checker1 = DimensionalChecker()
        report1 = checker1.check_axiom_set(explorer.axioms)

        checker2 = DimensionalChecker()
        report2 = checker2.check_axiom_set(explorer.axioms)

        assert report1.verdict == report2.verdict
        assert report1.checked == report2.checked
        assert report1.unknown_required == report2.unknown_required
        assert report1.unknown_coverage == report2.unknown_coverage
        assert len(report1.errors) == len(report2.errors)
        assert report1.checker_version == report2.checker_version
        assert report1.calibration_markers == report2.calibration_markers
        assert report1.inferred_dims == report2.inferred_dims


# =============================================
# F) FULL PIPELINE REGRESSION
# =============================================

class TestFullPipeline:
    """Run the full checker on the real axiom set."""

    def test_gate3_pass_on_real_axioms(self):
        """Gate 3 must PASS on the real axiom corpus."""
        from discovery.engine import CoAIOperandicsExplorer
        explorer = CoAIOperandicsExplorer(
            max_clauses=100, max_depth=3,
            min_interestingness=0.1)

        checker = DimensionalChecker()
        report = checker.check_axiom_set(explorer.axioms)

        assert report.verdict == "PASS", \
            f"Gate 3 verdict should be PASS, got {report.verdict}"
        assert report.errors == [], \
            f"No DimErrors expected: {report.errors}"
        assert report.unknown_required == 0, \
            f"No blocking unknowns: {report.unknown_required}"
        assert report.checked == len(explorer.axioms)
        assert len(report.inferred_dims) > 0, \
            "Should infer at least some variable dimensions"

    def test_regression_bad_axiom_detected(self):
        """Injecting ResourceCost(ID_M) = R_ZERO should fail
        (ENERGY != DIMENSIONLESS)."""
        m = mod_var("ID_M")
        bad_axiom = Equality(
            left=func("ResourceCost", Constant(name="ID_M", sort=MODULE)),
            right=const("R_ZERO"),
        )
        checker = DimensionalChecker()
        report = checker.check_axiom_set([bad_axiom], ["bad_axiom"])
        assert report.verdict == "FAIL", \
            f"Bad axiom should fail: {report.verdict}"
        assert len(report.errors) > 0
