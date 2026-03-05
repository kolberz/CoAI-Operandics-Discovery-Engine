import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from add_attention_axioms import categorize_lean_theorem


def test_matrix_mul_assoc_is_algebra():
    # Matrix.* should always be categorized as algebra
    cat = categorize_lean_theorem("Matrix.mul_assoc", typ="∀ ...", axioms=["propext"])
    assert cat == "algebra"


def test_matrix_transpose_transpose_is_algebra():
    cat = categorize_lean_theorem("Matrix.transpose_transpose", typ="∀ ...", axioms=["propext"])
    assert cat == "algebra"


def test_matrix_transpose_mul_is_algebra():
    cat = categorize_lean_theorem("Matrix.transpose_mul", typ="∀ ...", axioms=["propext"])
    assert cat == "algebra"


def test_stochasticattention_factorize_defaults_to_foundation_or_algebra():
    # Depending on your policy, you may decide StochasticAttention.* factorization counts as algebra.
    # If you keep the current conservative categorizer ("Matrix.* only"), it will fall through to foundation.
    # We allow either so the test doesn't fight your naming preference.
    cat = categorize_lean_theorem(
        "StochasticAttention.attnKernel_factorize",
        typ="∀ ... Matrix ...",  # optional hint; your categorizer may or may not use this
        axioms=["propext", "Classical.choice"]
    )
    assert cat in ("foundation", "algebra", "uncategorized")


# ---------------------------------------------------------------------------
# Synthetic pattern tests (future-proofing)
# These ensure the categorizer behaves for statistical/analytic theorems later,
# even if the current bundle doesn't include them yet.
# ---------------------------------------------------------------------------

def test_probability_theory_is_statistical():
    cat = categorize_lean_theorem(
        "ProbabilityTheory.HasSubgaussianMGF.measure_ge_le",
        typ="∀ ... MeasureTheory ...",
        axioms=["propext"]
    )
    assert cat == "statistical"


def test_measure_theory_is_statistical():
    cat = categorize_lean_theorem(
        "MeasureTheory.integral_map",
        typ="∀ ... MeasureTheory ...",
        axioms=["propext"]
    )
    assert cat == "statistical"


def test_real_exp_is_analytic():
    cat = categorize_lean_theorem(
        "Real.exp_add",
        typ="∀ x y : ℝ, Real.exp (x + y) = ...",
        axioms=["propext"]
    )
    assert cat == "analytic"


def test_trig_cos_is_analytic():
    cat = categorize_lean_theorem(
        "Real.cos_sub",
        typ="∀ x y : ℝ, Real.cos (x - y) = ...",
        axioms=["propext"]
    )
    assert cat == "analytic"


def test_fallback_foundation_when_only_foundational_axioms():
    cat = categorize_lean_theorem(
        "Some.Other.Lemma",
        typ=None,
        axioms=["propext", "Classical.choice", "Quot.sound"]
    )
    assert cat in ("foundation", "uncategorized")
