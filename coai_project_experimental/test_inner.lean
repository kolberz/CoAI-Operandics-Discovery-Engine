import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Probability.Distributions.Gaussian.Real

open MeasureTheory ProbabilityTheory Real Complex
open scoped InnerProductSpace

lemma real_inner_eq_mul (x y : ℝ) : ⟪x, y⟫_ℝ = y * x := rfl

lemma real_inner_yt (y t : ℝ) : ⟪y, t⟫_ℝ = t * y := rfl

lemma real_inner_y1 (y : ℝ) : ⟪y, 1⟫_ℝ = y := by
  calc
    ⟪y, 1⟫_ℝ = 1 * y := rfl
    _ = y := by ring

