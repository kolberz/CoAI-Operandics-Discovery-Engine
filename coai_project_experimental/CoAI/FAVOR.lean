import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.Probability.Notation
import Mathlib.Analysis.SpecialFunctions.Exponential
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Data.Fin.Basic
import Mathlib.Tactic.Positivity
import CoAI.GaussianCharFun

open scoped BigOperators InnerProductSpace
open MeasureTheory ProbabilityTheory Real

namespace StochasticAttention

variable {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]

set_option linter.unusedSimpArgs false
set_option linter.unnecessarySimpa false

-- Use E directly as our vector space (no abbrev needed)
abbrev Vec (E : Type*) := E

variable (ω : Ω → E)

-- Axiom 1 has been ELIMINATED and replaced by `expected_cos_gaussian_proof`
-- from CoAI.GaussianCharFun

-- The exact Softmax Kernel
noncomputable def ExactSoftmax (q k : E) : ℝ :=
  Real.exp (⟪q, k⟫_ℝ)

-- FAVOR+ Feature Map (m=1 single draw)
noncomputable def FavorPhi (ωs : E) (x : E) : Fin 2 → ℝ
  | 0 => Real.exp ((‖x‖ ^ 2) / 2) * Real.cos ⟪ωs, x⟫_ℝ
  | 1 => Real.exp ((‖x‖ ^ 2) / 2) * Real.sin ⟪ωs, x⟫_ℝ

lemma sum_fin2 (f : Fin 2 → ℝ) : (∑ i : Fin 2, f i) = f 0 + f 1 := by
  simpa using (Fin.sum_univ_two f)

-- The m=1 Proof (Level 2)
theorem favor_is_unbiased (q k : E)
    (h_gaussian : ∀ x : E,
      (volume.map (fun s => ⟪ω s, x⟫_ℝ)) = gaussianReal 0 (‖x‖ ^ 2).toNNReal) :
    (∫ s : Ω, ∑ i : Fin 2, FavorPhi (ω s) q i * FavorPhi (ω s) k i)
      = ExactSoftmax q k := by
  classical
  have hsum : (fun s : Ω => ∑ i : Fin 2, FavorPhi (ω s) q i * FavorPhi (ω s) k i) =
      (fun s : Ω => Real.exp (‖q‖ ^ 2 / 2) * Real.cos ⟪ω s, q⟫_ℝ * (Real.exp (‖k‖ ^ 2 / 2) * Real.cos ⟪ω s, k⟫_ℝ) +
        Real.exp (‖q‖ ^ 2 / 2) * Real.sin ⟪ω s, q⟫_ℝ * (Real.exp (‖k‖ ^ 2 / 2) * Real.sin ⟪ω s, k⟫_ℝ)) := by
    funext s; simp [FavorPhi]

  have htrig :
    (fun s =>
        Real.exp (‖q‖ ^ 2 / 2) * Real.cos ⟪ω s, q⟫_ℝ * (Real.exp (‖k‖ ^ 2 / 2) * Real.cos ⟪ω s, k⟫_ℝ) +
        Real.exp (‖q‖ ^ 2 / 2) * Real.sin ⟪ω s, q⟫_ℝ * (Real.exp (‖k‖ ^ 2 / 2) * Real.sin ⟪ω s, k⟫_ℝ))
      =
    (fun s =>
        Real.exp (‖q‖ ^ 2 / 2) * Real.exp (‖k‖ ^ 2 / 2) * Real.cos ⟪ω s, q - k⟫_ℝ) := by
    funext s
    have hinter : ⟪ω s, q - k⟫_ℝ = ⟪ω s, q⟫_ℝ - ⟪ω s, k⟫_ℝ := by
      simp [inner_sub_right]
    have hcos := (Real.cos_sub ⟪ω s, q⟫_ℝ ⟪ω s, k⟫_ℝ).symm
    rw [← hinter] at hcos
    calc
      Real.exp (‖q‖ ^ 2 / 2) * Real.cos ⟪ω s, q⟫_ℝ * (Real.exp (‖k‖ ^ 2 / 2) * Real.cos ⟪ω s, k⟫_ℝ) +
      Real.exp (‖q‖ ^ 2 / 2) * Real.sin ⟪ω s, q⟫_ℝ * (Real.exp (‖k‖ ^ 2 / 2) * Real.sin ⟪ω s, k⟫_ℝ)
        = (Real.exp (‖q‖ ^ 2 / 2) * Real.exp (‖k‖ ^ 2 / 2)) *
          (Real.cos ⟪ω s, q⟫_ℝ * Real.cos ⟪ω s, k⟫_ℝ + Real.sin ⟪ω s, q⟫_ℝ * Real.sin ⟪ω s, k⟫_ℝ) := by ring
      _ = Real.exp (‖q‖ ^ 2 / 2) * Real.exp (‖k‖ ^ 2 / 2) * Real.cos ⟪ω s, q - k⟫_ℝ := by
          rw [hcos]

  calc
    (∫ s : Ω, ∑ i : Fin 2, FavorPhi (ω s) q i * FavorPhi (ω s) k i)
      = ∫ s : Ω, Real.exp (‖q‖ ^ 2 / 2) * Real.exp (‖k‖ ^ 2 / 2) * Real.cos ⟪ω s, q - k⟫_ℝ := by rw [hsum, htrig]
    _ = (Real.exp (‖q‖ ^ 2 / 2) * Real.exp (‖k‖ ^ 2 / 2)) * ∫ s : Ω, Real.cos ⟪ω s, q - k⟫_ℝ := by
          exact integral_const_mul _ _
    _ = (Real.exp ((‖q‖ ^ 2) / 2) * Real.exp ((‖k‖ ^ 2) / 2)) * Real.exp (-(‖q - k‖ ^ 2) / 2) := by rw [StochasticAttention.expected_cos_gaussian_proof ω (h_gaussian) (q - k)]
    _ = ExactSoftmax q k := by
        have hnorm : ‖q - k‖ ^ 2 = ‖q‖ ^ 2 + ‖k‖ ^ 2 - 2 * ⟪q, k⟫_ℝ := by
          have := norm_sub_sq_real q k; linarith
        unfold ExactSoftmax
        set a : ℝ := ‖q‖ ^ 2 / 2
        set b : ℝ := ‖k‖ ^ 2 / 2
        set c : ℝ := -‖q - k‖ ^ 2 / 2
        calc
          Real.exp a * Real.exp b * Real.exp c
              = (Real.exp a * Real.exp b) * Real.exp c := rfl
          _ = Real.exp (a + b) * Real.exp c := by
                  rw [← Real.exp_add a b]
          _ = Real.exp ((a + b) + c) := by
                  rw [(Real.exp_add (a + b) c).symm]
          _ = Real.exp (a + b + c) := by
                  simp [add_assoc]
          _ = Real.exp (⟪q, k⟫_ℝ) := by
                  simp [a, b, c, add_assoc]
                  congr 1; linarith

-- ============================================================================
-- THE m-GENERALIZATION (Averaged Estimator Bridge)
-- ============================================================================

/-- Unbiasedness lifts from one draw to the average of `m` draws packaged in `ω : Ω → Fin m → E`. -/
theorem favor_is_unbiased_m
  (m : ℕ) (hm : 0 < m) (ω_m : Ω → Fin m → E) (q k : E)
  (h_gaussian : ∀ r : Fin m, ∀ x : E,
    (volume.map (fun s => ⟪ω_m s r, x⟫_ℝ)) = gaussianReal 0 (‖x‖ ^ 2).toNNReal)
  (h_int :
    ∀ r : Fin m,
      Integrable (fun s => ∑ i : Fin 2, FavorPhi (ω_m s r) q i * FavorPhi (ω_m s r) k i) volume) :
    (∫ s : Ω,
        ((1 / (m : ℝ)) *
          ∑ r : Fin m, ∑ i : Fin 2, FavorPhi (ω_m s r) q i * FavorPhi (ω_m s r) k i))
      =
      ExactSoftmax q k := by
  classical

  -- Nonzero casted m (eliminates "m = 0" branches)
  have hm0 : (m : ℝ) ≠ 0 := by
    exact_mod_cast (Nat.ne_of_gt hm)

  -- Define the per-r integrand, to keep later lines readable
  let f : Fin m → Ω → ℝ :=
    fun r s => ∑ i : Fin 2, FavorPhi (ω_m s r) q i * FavorPhi (ω_m s r) k i

  -- integrability for Finset.sum lemma (explicit Finset type!)
  have h_int_sum :
      ∀ r ∈ (Finset.univ : Finset (Fin m)), Integrable (f r) volume := by
    intro r _
    simpa [f] using h_int r

  -- per-feature unbiasedness (from Level 2)
  have hr : ∀ r : Fin m, (∫ s : Ω, f r s) = ExactSoftmax q k := by
    intro r
    -- your Level-2 lemma:
    -- favor_is_unbiased (ω := fun s => ω_m s r) q k (h_gaussian r)
    simpa [f] using (favor_is_unbiased (fun s => ω_m s r) q k (h_gaussian r))

  -- Now do the linearity chain cleanly with explicit Finset sums
  calc
    (∫ s : Ω, ( (1 / (m : ℝ)) * ∑ r : Fin m, f r s ))
        =
      (1 / (m : ℝ)) * ∫ s : Ω, (∑ r : Fin m, f r s) := by
        exact integral_const_mul _ _
    _ =
      (1 / (m : ℝ)) * (∑ r : Fin m, (∫ s : Ω, f r s)) := by
        -- integral of a finite sum
        congr 1; exact integral_finset_sum _ h_int_sum
    _ =
      (1 / (m : ℝ)) * (∑ _ : Fin m, ExactSoftmax q k) := by
        simp [hr]
    _ =
      (1 / (m : ℝ)) * ((m : ℝ) * ExactSoftmax q k) := by
        simp [Finset.sum_const, Finset.card_fin]
    _ =
      ExactSoftmax q k := by
        -- (1/m) * (m * c) = c
        field_simp [hm0]

end StochasticAttention
