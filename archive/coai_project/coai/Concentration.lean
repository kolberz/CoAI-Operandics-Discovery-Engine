import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.Tactic.Positivity
import CoAI.FAVOR

open MeasureTheory Real
open scoped BigOperators InnerProductSpace

namespace StochasticAttention

variable {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]

variable (m : ℕ)
variable (ω : Ω → Fin m → E)

/-- The averaged approximation error over m random features. -/
noncomputable def KernelError_m (q k : E) (s : Ω) : ℝ :=
  ((1 / (m : ℝ)) * ∑ r : Fin m,
      ∑ i : Fin 2, FavorPhi (ω s r) q i * FavorPhi (ω s r) k i)
    - ExactSoftmax q k

-- ============================================================================
-- THE ANALYTIC AXIOM (Option A: Direct Hoeffding/Sub-Gaussian Tail)
-- ============================================================================

-- Axiom 2 (favor_hoeffding_tail_bound_m) has been ELIMINATED.
-- The generic tail bound is now proven in CoAI.FavorSubGaussian, and we
-- accept the specific distribution's tail bound as a hypothesis here,
-- to be instantiated at deployment time when the specific random feature
-- measure is provided.

-- ============================================================================
-- LEVEL 3b TARGET: THE L0 HYPERVISOR DEPLOYMENT KNOB
-- ============================================================================

theorem favor_bound_delta
  (q k : E) (hm : 0 < m)
  (ε δ : ℝ) (hε : 0 < ε) (hδ : 0 < δ)
  (h_tail :
    (volume {s | ε ≤ |KernelError_m (ω := ω) (m := m) q k s|}).toReal ≤
      2 * Real.exp ( - ((m : ℝ) * ε^2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖)) ))
  (hm_req :
    Real.log (2 / δ) ≤ ((m : ℝ) * ε ^ 2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖))) :
  (volume {s | ε ≤ |KernelError_m (m := m) (ω := ω) q k s|}).toReal ≤ δ := by

  -- negate hm_req to compare exponents
  have h_neg :
      -(((m : ℝ) * ε ^ 2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖)))
        ≤ -(Real.log (2 / δ)) := by
    exact neg_le_neg hm_req

  have h_exp :
      Real.exp ( -(((m : ℝ) * ε ^ 2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖))) )
        ≤ Real.exp (-(Real.log (2 / δ))) := by
    exact (Real.exp_le_exp).2 h_neg

  have h_two_pos : (0 : ℝ) ≤ 2 := by positivity

  have h_mul :
      2 * Real.exp ( -(((m : ℝ) * ε ^ 2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖))) )
        ≤ 2 * Real.exp (-(Real.log (2 / δ))) := by
    exact mul_le_mul_of_nonneg_left h_exp h_two_pos

  -- simplify RHS: 2 * exp(-log(2/δ)) = δ
  have h_log_pos : 0 < (2 / δ) := by
    have : (0 : ℝ) < 2 := by positivity
    exact div_pos this hδ

  have hd_ne : δ ≠ 0 := hδ.ne'

  have hsimp : 2 * Real.exp (-(Real.log (2 / δ))) = δ := by
    simp only [Real.exp_neg, Real.exp_log h_log_pos]
    field_simp [hd_ne, two_ne_zero]

  -- final chain
  calc
    (volume {s | ε ≤ |KernelError_m (m := m) (ω := ω) q k s|}).toReal
        ≤ 2 * Real.exp ( - (((m : ℝ) * ε ^ 2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖))) ) := by
          have := h_tail; simp only [neg_div] at this ⊢; exact this
    _ ≤ 2 * Real.exp (-(Real.log (2 / δ))) := h_mul
    _ = δ := hsimp

end StochasticAttention
