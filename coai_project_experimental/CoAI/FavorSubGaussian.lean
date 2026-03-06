import Mathlib.Probability.Moments.SubGaussian
import Mathlib.Probability.Notation
import Mathlib.Analysis.SpecialFunctions.Exponential
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Linarith

open MeasureTheory ProbabilityTheory Real
open scoped BigOperators

set_option autoImplicit false

namespace CoAI
namespace SubGaussian

variable {Ω : Type*} [MeasureSpace Ω]
variable (μ : Measure Ω) [IsProbabilityMeasure μ]

/- Helper: union bound for `μ.real`.  We unfold `μ.real` as `toReal (μ _)`
   and use `measure_union_le` on ENNReal, then `toReal` monotonicity + `toReal_add`.
   This is standard and works because probability measures are finite. -/
lemma real_union_le (A B : Set Ω) :
    μ.real (A ∪ B) ≤ μ.real A + μ.real B := by
  -- unfold μ.real = toReal (μ _)
  simp [Measure.real]
  have hle : μ (A ∪ B) ≤ μ A + μ B := by
    simpa using (measure_union_le A B)
  have hA : μ A ≠ (⊤ : ENNReal) := measure_ne_top μ A
  have hB : μ B ≠ (⊤ : ENNReal) := measure_ne_top μ B
  have hsum : μ A + μ B ≠ (⊤ : ENNReal) := by simp [hA, hB]
  have h_toReal :
      (μ (A ∪ B)).toReal ≤ (μ A + μ B).toReal :=
    (ENNReal.toReal_le_toReal (measure_ne_top μ (A ∪ B)) hsum).2 hle
  simpa [ENNReal.toReal_add, hA, hB] using h_toReal

/-
Pinned Mathlib often uses `c : ℝ≥0` (NNReal) for HasSubgaussianMGF.
We parameterize with `c : NNReal` and coerce to ℝ where needed.
-/
variable (X : Ω → ℝ) (c : NNReal)

/-- One-sided tail bound from `HasSubgaussianMGF`. -/
theorem right_tail
    (h : HasSubgaussianMGF X c μ) (ε : ℝ) (hε : 0 ≤ ε) :
    μ.real {ω | ε ≤ X ω} ≤ Real.exp (-ε ^ 2 / (2 * (c : ℝ))) := by
  -- Mathlib lemma typically states exactly this shape (with `↑c` coerced to ℝ)
  simpa using h.measure_ge_le (ε := ε) hε

/-- Two-sided tail bound derived via union bound on `X` and `-X`. -/
theorem abs_tail
    (h : HasSubgaussianMGF X c μ) (ε : ℝ) (hε : 0 ≤ ε) :
    μ.real {ω | ε ≤ |X ω|} ≤ 2 * Real.exp (-ε ^ 2 / (2 * (c : ℝ))) := by
  classical
  let A : Set Ω := {ω | ε ≤ X ω}
  let B : Set Ω := {ω | ε ≤ -X ω}

  have hset : {ω | ε ≤ |X ω|} = A ∪ B := by
    ext ω
    -- `le_abs` gives: ε ≤ |x| ↔ ε ≤ x ∨ ε ≤ -x
    simp [A, B, le_abs]

  have hneg : HasSubgaussianMGF (fun ω => -X ω) c μ := by
    simpa using h.neg

  have hA : μ.real A ≤ Real.exp (-ε ^ 2 / (2 * (c : ℝ))) := by
    simpa [A] using (h.measure_ge_le (ε := ε) hε)

  have hB : μ.real B ≤ Real.exp (-ε ^ 2 / (2 * (c : ℝ))) := by
    simpa [B] using (hneg.measure_ge_le (ε := ε) hε)

  calc
    μ.real {ω | ε ≤ |X ω|} = μ.real (A ∪ B) := by simp [hset]
    _ ≤ μ.real A + μ.real B := real_union_le (μ := μ) A B
    _ ≤ Real.exp (-ε ^ 2 / (2 * (c : ℝ))) + Real.exp (-ε ^ 2 / (2 * (c : ℝ))) := by
          exact add_le_add hA hB
    _ = 2 * Real.exp (-ε ^ 2 / (2 * (c : ℝ))) := by ring

/-- δ-form corollary with log-scaling. -/
theorem abs_tail_le_delta
    (h : HasSubgaussianMGF X c μ)
    (ε δ : ℝ) (hε : 0 < ε) (hδ : 0 < δ)
    (hreq : Real.log (2 / δ) ≤ (ε ^ 2) / (2 * (c : ℝ))) :
    μ.real {ω | ε ≤ |X ω|} ≤ δ := by
  have h0 : 0 ≤ ε := le_of_lt hε
  have ht := abs_tail (μ := μ) (X := X) (c := c) h ε h0

  have hneg : -(ε ^ 2) / (2 * (c : ℝ)) ≤ -(Real.log (2 / δ)) := by
    -- `neg_div` rewrites -(a/b) = (-a)/b, matching the expected shape
    simpa [neg_div] using (neg_le_neg hreq)

  have hexp :
      Real.exp ( -(ε ^ 2) / (2 * (c : ℝ)) )
        ≤ Real.exp (-(Real.log (2 / δ))) := by
    exact (Real.exp_le_exp).2 hneg

  have htwo : (0 : ℝ) ≤ 2 := by positivity
  have hmul :
      2 * Real.exp ( -(ε ^ 2) / (2 * (c : ℝ)) )
        ≤ 2 * Real.exp (-(Real.log (2 / δ))) := by
    exact mul_le_mul_of_nonneg_left hexp htwo

  have h_log_pos : 0 < (2 / δ) := by
    have : (0 : ℝ) < 2 := by positivity
    exact div_pos this hδ

  have hd_ne : δ ≠ 0 := hδ.ne'

  have hsimp : 2 * Real.exp (-(Real.log (2 / δ))) = δ := by
    simp only [Real.exp_neg, Real.exp_log h_log_pos]
    field_simp [hd_ne, two_ne_zero]

  calc
    μ.real {ω | ε ≤ |X ω|} ≤ 2 * Real.exp ( -ε ^ 2 / (2 * (c : ℝ)) ) := ht
    _ ≤ 2 * Real.exp (-(Real.log (2 / δ))) := hmul
    _ = δ := hsimp

end SubGaussian
end CoAI
