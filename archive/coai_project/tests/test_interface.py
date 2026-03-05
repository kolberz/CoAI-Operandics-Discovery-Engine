"""
tests/test_interface.py  (v3.1.1)

Encodes the exact Lean ↔ Python correspondence.
If any test fails, the operational code has drifted from the formal kernel.
"""
import pytest
import math
import warnings
from coai.interface import (
    Contract,
    PhysInterval,
    CompositionResult,
    RiskProfile,
    ValueParams,
    CompatibilityVerdict,
    compute_value_objective_interval,
    DIM_DIMENSIONLESS,
    Dimension,
)
from coai.interface import SMTCompatibilityChecker

class TestContractInvariants:
    def test_eps_nonneg(self):
        with pytest.raises(ValueError, match="eps_nonneg"):
            Contract(lambda s: True, lambda s: True, -0.1)

    def test_nan_rejected(self):
        with pytest.raises(ValueError, match="NaN"):
            Contract(lambda s: True, lambda s: True, float("nan"))

    def test_non_numeric_rejected(self):
        with pytest.raises(TypeError, match="numeric"):
            Contract(lambda s: True, lambda s: True, "high")

    def test_epsilon_above_one_allowed(self):
        """Lean Contract has no upper bound on epsilon."""
        c = Contract(lambda s: True, lambda s: True, 1.5)
        assert c.epsilon == 1.5
        assert c.is_vacuous

    def test_epsilon_zero_valid(self):
        c = Contract(lambda s: True, lambda s: True, 0.0)
        assert c.epsilon == 0.0
        assert not c.is_vacuous


class TestComposition:
    def test_union_bound(self):
        """Matches Lean Theorem 2.1: ε_composed = ε₁ + ε₂"""
        c1 = Contract(lambda s: True, lambda s: True, 0.01)
        c2 = Contract(lambda s: True, lambda s: True, 0.02)
        result = CompositionResult.seq_compose(c1, c2)
        assert result.epsilon_bound == pytest.approx(0.03)

    def test_not_independent_failure(self):
        """We use union bound (ε₁+ε₂), NOT 1-(1-ε₁)(1-ε₂)."""
        c1 = Contract(lambda s: True, lambda s: True, 0.5)
        c2 = Contract(lambda s: True, lambda s: True, 0.5)
        result = CompositionResult.seq_compose(c1, c2)
        assert result.epsilon_bound == pytest.approx(1.0)
        assert result.epsilon_bound != pytest.approx(0.75)

    def test_composition_can_exceed_one(self):
        """ε₁ + ε₂ > 1 is valid (vacuously true bound)."""
        c1 = Contract(lambda s: True, lambda s: True, 0.6)
        c2 = Contract(lambda s: True, lambda s: True, 0.6)
        result = CompositionResult.seq_compose(c1, c2)
        assert result.epsilon_bound == pytest.approx(1.2)

    def test_zero_plus_zero(self):
        c1 = Contract(lambda s: True, lambda s: True, 0.0)
        c2 = Contract(lambda s: True, lambda s: True, 0.0)
        result = CompositionResult.seq_compose(c1, c2)
        assert result.epsilon_bound == 0.0


class TestRiskProfile:
    def test_expected_risk(self):
        r = RiskProfile(epsilon=0.03, consequence=10000.0)
        assert r.expected_risk == pytest.approx(300.0)

    def test_zero_consequence(self):
        r = RiskProfile(epsilon=1.0, consequence=0.0)
        assert r.expected_risk == 0.0

    def test_zero_epsilon(self):
        r = RiskProfile(epsilon=0.0, consequence=99999.0)
        assert r.expected_risk == 0.0

    def test_vacuous_epsilon_caps_at_one(self):
        """ε > 1 is allowed but expected_risk caps the probability at 1."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = RiskProfile(epsilon=1.5, consequence=100.0)
        assert r.expected_risk == pytest.approx(100.0)  # min(1.5, 1.0) * 100
        assert r.is_vacuous

    def test_negative_epsilon_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            RiskProfile(epsilon=-0.01, consequence=100.0)

    def test_negative_consequence_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            RiskProfile(epsilon=0.5, consequence=-1.0)

    def test_vacuous_warns(self):
        with pytest.warns(UserWarning, match="vacuous"):
            RiskProfile(epsilon=1.2, consequence=100.0)


class TestIntervalArithmetic:
    def test_inverted_rejected(self):
        with pytest.raises(ValueError, match="Inverted"):
            PhysInterval(5.0, 1.0, DIM_DIMENSIONLESS)

    def test_nan_rejected(self):
        with pytest.raises(ValueError, match="NaN"):
            PhysInterval(float("nan"), 1.0, DIM_DIMENSIONLESS)

    def test_dimension_mismatch_add(self):
        a = PhysInterval(1.0, 2.0, Dimension(energy=1))
        b = PhysInterval(1.0, 2.0, Dimension(info=1))
        with pytest.raises(TypeError, match="mismatch"):
            a + b

    def test_addition(self):
        a = PhysInterval(1.0, 2.0, DIM_DIMENSIONLESS)
        b = PhysInterval(3.0, 4.0, DIM_DIMENSIONLESS)
        c = a + b
        assert c.lo == pytest.approx(4.0)
        assert c.hi == pytest.approx(6.0)

    def test_point_interval(self):
        p = PhysInterval(3.0, 3.0, DIM_DIMENSIONLESS)
        assert p.lo == p.hi


class TestValueObjective:
    def test_bounds_direction(self):
        params = ValueParams(lambda_R=1.0, lambda_C=1.0, lambda_v=1.0)
        u = PhysInterval(10.0, 20.0, DIM_DIMENSIONLESS)
        r = PhysInterval(1.0, 5.0, DIM_DIMENSIONLESS)
        c = PhysInterval(2.0, 3.0, DIM_DIMENSIONLESS)
        v = compute_value_objective_interval(u, r, c, params)
        assert v.lo == pytest.approx(10.0 - 5.0 - 3.0) 
        assert v.hi == pytest.approx(20.0 - 1.0 - 2.0)  

    def test_zero_risk_aversion(self):
        params = ValueParams(lambda_R=0.0, lambda_C=1.0, lambda_v=1.0)
        u = PhysInterval(10.0, 10.0, DIM_DIMENSIONLESS)
        r = PhysInterval(999.0, 999.0, DIM_DIMENSIONLESS)
        c = PhysInterval(3.0, 3.0, DIM_DIMENSIONLESS)
        v = compute_value_objective_interval(u, r, c, params)
        assert v.lo == pytest.approx(10.0 - 3.0)

    def test_dimension_enforcement(self):
        params = ValueParams(lambda_R=1.0, lambda_C=1.0, lambda_v=1.0)
        u = PhysInterval(10.0, 20.0, Dimension(energy=1)) 
        r = PhysInterval(1.0, 5.0, DIM_DIMENSIONLESS)
        c = PhysInterval(2.0, 3.0, DIM_DIMENSIONLESS)
        with pytest.raises(TypeError, match="dimensionless"):
            compute_value_objective_interval(u, r, c, params)


class TestCompatibilityVerdict:
    def test_no_checker_returns_untrusted(self):
        c = Contract(lambda s: True, lambda s: True, 0.1)
        verdict = c.check_compatibility(c, checker=None)
        assert verdict == CompatibilityVerdict.UNTRUSTED

    def test_no_smt_strings_returns_untrusted(self):
        c1 = Contract(lambda s: True, lambda s: True, 0.1) 
        c2 = Contract(lambda s: True, lambda s: True, 0.1)
        checker = SMTCompatibilityChecker()
        verdict = c1.check_compatibility(c2, checker=checker)
        assert verdict == CompatibilityVerdict.UNTRUSTED
