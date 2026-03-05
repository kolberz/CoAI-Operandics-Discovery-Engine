import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Analysis.InnerProductSpace.Continuous
import Mathlib.Probability.Distributions.Gaussian.Real
import Mathlib.MeasureTheory.Measure.MeasureSpaceDef
import Mathlib.MeasureTheory.Integral.Bochner.Basic

open MeasureTheory ProbabilityTheory Real Complex
open scoped InnerProductSpace

lemma integrable_of_ae_bound_const {Ω F : Type*} [MeasurableSpace Ω] {μ : Measure Ω} [IsFiniteMeasure μ]
    [NormedAddCommGroup F] {f : Ω → F} (C : ℝ)
    (hmeas : AEStronglyMeasurable f μ) (hbound : ∀ᵐ ω ∂μ, ‖f ω‖ ≤ C) : Integrable f μ := by
  have hC : Integrable (fun _ : Ω => (C : ℝ)) μ := integrable_const (C : ℝ)
  exact hC.mono' hmeas hbound

lemma test_int (t : ℝ) : Integrable (fun y : ℝ => cexp (↑⟪y, t⟫_ℝ * I)) (gaussianReal 0 1) := by
  have h_meas : AEStronglyMeasurable (fun y : ℝ => cexp (↑⟪y, t⟫_ℝ * I)) (gaussianReal 0 1) := by
    apply Continuous.aestronglyMeasurable
    exact Continuous.cexp (Continuous.mul (continuous_ofReal.comp (Continuous.inner continuous_id continuous_const)) continuous_const)
  have h_bound : ∀ᵐ y ∂(gaussianReal 0 1), ‖cexp (↑⟪y, t⟫_ℝ * I)‖ ≤ (1:ℝ) := by
    filter_upwards
    intro y
    simp [Complex.norm_exp_ofReal_mul_I]
  exact integrable_of_ae_bound_const 1 h_meas h_bound

lemma test_aemeasurable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
    (ω : Ω → E)
    (x : E)
    (h_gaussian : Measure.map (fun s => ⟪ω s, x⟫_ℝ) volume = gaussianReal 0 (‖x‖ ^ 2).toNNReal) :
    AEMeasurable (fun s => ⟪ω s, x⟫_ℝ) volume := by
  by_contra h_not_meas
  have h_map_zero := Measure.map_of_not_aemeasurable h_not_meas
  rw [h_gaussian] at h_map_zero
  have h_prob : IsProbabilityMeasure (gaussianReal 0 (‖x‖ ^ 2).toNNReal) := instIsProbabilityMeasureGaussianReal 0 (‖x‖ ^ 2).toNNReal
  have h_ne_zero := @IsProbabilityMeasure.ne_zero ℝ _ (gaussianReal 0 (‖x‖ ^ 2).toNNReal) h_prob
  exact h_ne_zero h_map_zero

