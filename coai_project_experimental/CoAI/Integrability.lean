/-
  Integrability.lean
  Provides reusable integrability lemmas for trigonometric functions and
  feature map integrands over finite probability measures, eliminating
  the need for `sorryAx` when commuting expectations and integrals.
-/
import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.Probability.Independence.Basic
import Mathlib.Analysis.InnerProductSpace.Continuous
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic
import Mathlib.Analysis.InnerProductSpace.Basic

open scoped BigOperators Real InnerProductSpace
open MeasureTheory ProbabilityTheory

namespace StochasticAttention

variable {Ω : Type*} [MeasurableSpace Ω] {μ : Measure Ω} [IsFiniteMeasure μ]
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [MeasurableSpace E] [BorelSpace E]

/-- 
  If `‖f ω‖ ≤ C` a.e. and `f` is a.e.-strongly measurable, then `f` is integrable.
  This lemma handles arbitrary bounded integrands over finite measures.
-/
lemma integrable_of_ae_bound_const
    {F : Type*} [NormedAddCommGroup F]
    {f : Ω → F} (C : ℝ)
    (hmeas : AEStronglyMeasurable f μ)
    (hbound : ∀ᵐ ω ∂μ, ‖f ω‖ ≤ C) :
    Integrable f μ := by
  have hC : Integrable (fun _ : Ω => (C : ℝ)) μ := integrable_const (C : ℝ)
  exact hC.mono' hmeas hbound

-- ============================================================================
-- TRIGONOMETRIC INTEGRABILITY
-- ============================================================================

variable {μ : Measure E} [IsProbabilityMeasure μ]

/-- Cosine integrability for inner products: 
    Integrable (fun ω => cos ⟪ω, x⟫) μ -/
lemma integrable_cos_inner (x : E) :
    Integrable (fun ω : E => Real.cos ⟪ω, x⟫_ℝ) μ := by
  have hmeas : AEStronglyMeasurable (fun ω : E => Real.cos ⟪ω, x⟫_ℝ) μ := by
    exact (Continuous.inner continuous_id continuous_const).measurable.cos.aestronglyMeasurable
  have hbound : ∀ᵐ ω ∂μ, ‖Real.cos ⟪ω, x⟫_ℝ‖ ≤ (1:ℝ) := by
    filter_upwards with ω
    simpa [Real.norm_eq_abs] using (Real.abs_cos_le_one (⟪ω, x⟫_ℝ))
  exact integrable_of_ae_bound_const (μ := μ) (f := fun ω => Real.cos ⟪ω, x⟫_ℝ) 1 hmeas hbound

/-- Sine integrability for inner products:
    Integrable (fun ω => sin ⟪ω, x⟫) μ -/
lemma integrable_sin_inner (x : E) :
    Integrable (fun ω : E => Real.sin ⟪ω, x⟫_ℝ) μ := by
  have hmeas : AEStronglyMeasurable (fun ω : E => Real.sin ⟪ω, x⟫_ℝ) μ := by
    exact (Continuous.inner continuous_id continuous_const).measurable.sin.aestronglyMeasurable
  have hbound : ∀ᵐ ω ∂μ, ‖Real.sin ⟪ω, x⟫_ℝ‖ ≤ (1:ℝ) := by
    filter_upwards with ω
    simpa [Real.norm_eq_abs] using (Real.abs_sin_le_one (⟪ω, x⟫_ℝ))
  exact integrable_of_ae_bound_const (μ := μ) (f := fun ω => Real.sin ⟪ω, x⟫_ℝ) 1 hmeas hbound

/-- Scaled cos integrability: Integrable (fun ω => C * cos ⟪ω, x⟫) μ -/
lemma integrable_const_mul_cos_inner (x : E) (C : ℝ) :
    Integrable (fun ω : E => C * Real.cos ⟪ω, x⟫_ℝ) μ := by
  have : Integrable (fun ω : E => Real.cos ⟪ω, x⟫_ℝ) μ := integrable_cos_inner x
  simpa [mul_assoc] using this.const_mul C

/-- Integrability of the feature map: Integrable (fun ω => c * cos ⟪ω, q - k⟫) μ -/
lemma integrable_feature_map_integrand (q k : E) :
    Integrable (fun ω : E => (Real.exp (‖q‖^2/2) * Real.exp (‖k‖^2/2)) * Real.cos ⟪ω, q - k⟫_ℝ) μ := by
  exact integrable_const_mul_cos_inner (q - k) (Real.exp (‖q‖^2/2) * Real.exp (‖k‖^2/2))

end StochasticAttention
