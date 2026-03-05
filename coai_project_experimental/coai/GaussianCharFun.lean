/-
  GaussianCharFun.lean
  Bridge theorem: Proves `expected_cos_gaussian` from Mathlib's
  `charFun_gaussianReal` instead of postulating it as an axiom.

  Strategy:
    charFun_gaussianReal with μ=0, v=1 gives:
      charFun (gaussianReal 0 1) t = cexp (- t² / 2)
    The charFun is defined as  ∫ x, exp(i t x) dμ(x).
    Taking the real part gives  ∫ x, cos(t x) dμ(x) = exp(- t² / 2).
    For the inner product space version, we reduce ⟪ω,x⟫ to a 1D
    projection and apply the 1D result.
-/
import Mathlib.Probability.Distributions.Gaussian.Real
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic
import CoAI.Integrability

open MeasureTheory ProbabilityTheory Real Complex
open scoped BigOperators InnerProductSpace

namespace StochasticAttention

-- ============================================================================
-- 1D RESULT: ∫ cos(t·x) d(gaussianReal 0 1)(x) = exp(-t²/2)
-- ============================================================================

lemma real_inner_eq_mul (x y : ℝ) : ⟪x, y⟫_ℝ = x * y := by
  change y * x = x * y
  ring

/-- The standard Normal(0,1) measure on ℝ. -/
noncomputable def stdGaussian : Measure ℝ := gaussianReal 0 1

instance : IsProbabilityMeasure stdGaussian :=
  instIsProbabilityMeasureGaussianReal 0 1

/-- Integral of cos(t·x) under the standard Gaussian equals exp(-t²/2).
    Derived directly from Mathlib's `charFun_gaussianReal`.
-/
theorem integral_cos_stdGaussian (t : ℝ) :
    (∫ x : ℝ, Real.cos (t * x) ∂stdGaussian) = Real.exp (-(t ^ 2) / 2) := by
  have hcf := charFun_gaussianReal (μ := 0) (v := 1) t
  
  have h_re : (charFun stdGaussian t).re = (cexp (↑(-(t ^ 2) / 2 : ℝ))).re := by
    have h_std : stdGaussian = gaussianReal 0 1 := rfl
    rw [h_std]
    rw [hcf]
    push_cast
    congr 2
    ring
    
  have h_rhs : (cexp (↑(-(t ^ 2) / 2 : ℝ))).re = Real.exp (-(t ^ 2) / 2) := by
    simp only [Complex.exp_ofReal_re]
  
  have h_int : Integrable (fun y : ℝ => cexp (↑⟪y, t⟫_ℝ * I)) stdGaussian := by
    have h_meas : AEStronglyMeasurable (fun y : ℝ => cexp (↑⟪y, t⟫_ℝ * I)) stdGaussian := by
      apply Continuous.aestronglyMeasurable
      exact Continuous.cexp (Continuous.mul (continuous_ofReal.comp (Continuous.inner continuous_id continuous_const)) continuous_const)
    have h_bound : ∀ᵐ y ∂stdGaussian, ‖cexp (↑⟪y, t⟫_ℝ * I)‖ ≤ (1:ℝ) := by
      filter_upwards
      intro y
      simp [Complex.norm_exp_ofReal_mul_I]
    exact integrable_of_ae_bound_const 1 h_meas h_bound
  
  have h_lhs : (charFun stdGaussian t).re = ∫ x : ℝ, Real.cos (t * x) ∂stdGaussian := by
    have h_std : stdGaussian = gaussianReal 0 1 := rfl
    rw [h_std]
    unfold charFun
    have h_rw : RCLike.re (∫ y : ℝ, cexp (↑⟪y, t⟫_ℝ * I) ∂gaussianReal 0 1) = ∫ y : ℝ, RCLike.re (cexp (↑⟪y, t⟫_ℝ * I)) ∂gaussianReal 0 1 := (integral_re h_int).symm
    change RCLike.re (∫ y : ℝ, cexp (↑⟪y, t⟫_ℝ * I) ∂gaussianReal 0 1) = _
    rw [h_rw]
    congr 1
    ext y
    have h_yt : ⟪y, t⟫_ℝ = t * y := by
      rw [real_inner_eq_mul y t]
      ring
    rw [h_yt]
    have h_euler : cexp (↑(t * y) * I) = Complex.cos ↑(t * y) + Complex.sin ↑(t * y) * I := by
      exact Complex.exp_mul_I ↑(t * y)
    rw [h_euler]
    change (Complex.cos ↑(t * y) + Complex.sin ↑(t * y) * I).re = _
    rw [←Complex.ofReal_cos, ←Complex.ofReal_sin]
    simp only [Complex.add_re, Complex.mul_re, Complex.I_re, Complex.I_im, Complex.ofReal_re, Complex.ofReal_im]
    ring
  
  rw [h_rhs] at h_re
  rw [h_lhs] at h_re
  exact h_re


-- ============================================================================
-- LIFTING TO INNER PRODUCT SPACES
-- ============================================================================

/-- Identifies the pushforward measure of the Gaussian along a 1D projection. -/
lemma map_inner_gaussian_eq_gaussian
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
    (ω : Ω → E)
    (h_gaussian : ∀ x : E, (volume.map (fun s => ⟪ω s, x⟫_ℝ)) = gaussianReal 0 (‖x‖ ^ 2).toNNReal)
    (x : E) : 
    (volume.map (fun s => ⟪ω s, x⟫_ℝ)) = gaussianReal 0 (‖x‖ ^ 2).toNNReal :=
  h_gaussian x

/--
  The core theorem that replaces the former axiom.
-/
theorem expected_cos_gaussian_proof
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
    (ω : Ω → E)
    (h_gaussian : ∀ x : E, (volume.map (fun s => ⟪ω s, x⟫_ℝ)) = gaussianReal 0 (‖x‖ ^ 2).toNNReal)
    (x : E) :
    (∫ s : Ω, Real.cos ⟪ω s, x⟫_ℝ) = Real.exp (-(‖x‖ ^ 2) / 2) := by
  
  have h_push : (∫ s : Ω, Real.cos ⟪ω s, x⟫_ℝ) = ∫ t : ℝ, Real.cos t ∂(volume.map (fun s => ⟪ω s, x⟫_ℝ)) := by
    rw [integral_map]
    · by_contra h_not_meas
      have h_map_zero := Measure.map_of_not_aemeasurable h_not_meas
      rw [h_gaussian] at h_map_zero
      have h_prob : IsProbabilityMeasure (gaussianReal 0 (‖x‖ ^ 2).toNNReal) := instIsProbabilityMeasureGaussianReal 0 (‖x‖ ^ 2).toNNReal
      have h_ne_zero := @IsProbabilityMeasure.ne_zero ℝ _ (gaussianReal 0 (‖x‖ ^ 2).toNNReal) h_prob
      exact h_ne_zero h_map_zero
    · exact continuous_cos.aestronglyMeasurable

  rw [h_push]
  rw [map_inner_gaussian_eq_gaussian ω h_gaussian x]
  
  have hcf := charFun_gaussianReal (μ := 0) (v := (‖x‖ ^ 2).toNNReal) 1
  
  have h_re : (charFun (gaussianReal 0 (‖x‖ ^ 2).toNNReal) 1).re = (cexp (↑(-(‖x‖^2) / 2 : ℝ))).re := by
    have h_toNNReal_eq : ((‖x‖ ^ 2).toNNReal : ℝ) = ‖x‖ ^ 2 := Real.coe_toNNReal (‖x‖ ^ 2) (sq_nonneg ‖x‖)
    rw [h_toNNReal_eq] at hcf
    rw [hcf]
    push_cast
    congr 2
    ring
    
  have h_rhs : (cexp (↑(-(‖x‖^2) / 2 : ℝ))).re = Real.exp (-(‖x‖^2) / 2) := by
    simp only [Complex.exp_ofReal_re]
    
  have h_int : Integrable (fun y : ℝ => (Complex.exp (↑⟪y, 1⟫_ℝ * I))) (gaussianReal 0 (‖x‖ ^ 2).toNNReal) := by
    have h_meas : AEStronglyMeasurable (fun y : ℝ => cexp (↑⟪y, 1⟫_ℝ * I)) (gaussianReal 0 (‖x‖ ^ 2).toNNReal) := by
      apply Continuous.aestronglyMeasurable
      exact Continuous.cexp (Continuous.mul (continuous_ofReal.comp (Continuous.inner continuous_id continuous_const)) continuous_const)
    have h_bound : ∀ᵐ y ∂(gaussianReal 0 (‖x‖ ^ 2).toNNReal), ‖cexp (↑⟪y, 1⟫_ℝ * I)‖ ≤ (1:ℝ) := by
      filter_upwards
      intro y
      simp [Complex.norm_exp_ofReal_mul_I]
    exact integrable_of_ae_bound_const 1 h_meas h_bound

  have h_lhs : (charFun (gaussianReal 0 (‖x‖ ^ 2).toNNReal) 1).re = ∫ y : ℝ, Real.cos y ∂ (gaussianReal 0 (‖x‖ ^ 2).toNNReal) := by
    unfold charFun
    have h_rw : RCLike.re (∫ y : ℝ, cexp (↑⟪y, 1⟫_ℝ * I) ∂gaussianReal 0 (‖x‖ ^ 2).toNNReal) = ∫ y : ℝ, RCLike.re (cexp (↑⟪y, 1⟫_ℝ * I)) ∂gaussianReal 0 (‖x‖ ^ 2).toNNReal := (integral_re h_int).symm
    change RCLike.re (∫ y : ℝ, cexp (↑⟪y, 1⟫_ℝ * I) ∂gaussianReal 0 (‖x‖ ^ 2).toNNReal) = _
    rw [h_rw]
    congr 1
    ext y
    have h_y1 : ⟪y, 1⟫_ℝ = y := by
      rw [real_inner_eq_mul y 1]
      ring
    rw [h_y1]
    have h_euler : cexp (↑y * I) = Complex.cos ↑y + Complex.sin ↑y * I := by
      exact Complex.exp_mul_I ↑y
    rw [h_euler]
    change (Complex.cos ↑y + Complex.sin ↑y * I).re = _
    rw [←Complex.ofReal_cos, ←Complex.ofReal_sin]
    simp only [Complex.add_re, Complex.mul_re, Complex.I_re, Complex.I_im, Complex.ofReal_re, Complex.ofReal_im]
    ring

  rw [← h_lhs]
  rw [h_re]
  rw [h_rhs]

end StochasticAttention
