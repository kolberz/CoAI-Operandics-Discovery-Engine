import Mathlib.Probability.ProbabilityMassFunction.Basic
import Mathlib.Probability.ProbabilityMassFunction.Monad
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.MeasureTheory.Integral.Lebesgue.Markov
import Mathlib.Topology.Instances.ENNReal.Lemmas
import Mathlib.Tactic.Linarith
import Mathlib.Data.Real.Basic
import Mathlib.Probability.Martingale.Basic
import Mathlib.Probability.Process.Stopping
import Mathlib.Probability.Process.HittingTime
import Mathlib.Probability.Martingale.OptionalStopping

open MeasureTheory ENNReal Filter Set ProbabilityTheory
open scoped BigOperators Topology

noncomputable section

namespace CoAI.Control

/-!
## 1) PMF → Measure bridge + PMF Markov inequality
We use a discrete measurable space (everything measurable), and `Countable α`
so we can use `MeasureTheory.lintegral_eq_tsum`.
-/

section PMF

variable {α : Type*} [Countable α]
local instance : MeasurableSpace α := ⊤

omit [Countable α] in
lemma measurable_of_top_local {f : α → ℝ≥0∞} : Measurable f :=
  fun _ _ => trivial

local instance : MeasurableSingletonClass α := ⟨fun _ => trivial⟩

/-- Bridge lemma (canonical): `∫⁻ f d(p.toMeasure) = ∑' x, p x * f x`. -/
theorem pmf_lintegral_eq_tsum (p : PMF α) (f : α → ℝ≥0∞) :
    (∫⁻ x, f x ∂ p.toMeasure) = ∑' x, p x * f x := by
  have := MeasureTheory.lintegral_countable' (μ := p.toMeasure) f
  rw [this]
  congr 1; ext x
  have h_sing : p.toMeasure {x} = p x := PMF.toMeasure_apply_singleton p x (MeasurableSet.singleton _)
  rw [h_sing, mul_comm]

/-- Markov inequality specialized to PMFs (multiplicative form). -/
theorem pmf_markov_ineq_base (p : PMF α) (f : α → ℝ≥0∞) (ε : ℝ≥0∞) :
    ε * p.toMeasure {x | ε ≤ f x} ≤ ∑' x, p x * f x := by
  classical
  rw [← pmf_lintegral_eq_tsum]
  exact MeasureTheory.mul_meas_ge_le_lintegral measurable_of_top_local ε

end PMF

/-!
## 2) Algebraic drift bound
Cast-free induction using `n • δ`, then rewrite to `(n:ℝ)*δ` at the end.
-/

section Drift

/-- Drift bound without ℕ→ℝ cast hassles (`n • δ`). -/
theorem algebraic_drift_bound_nsmul (V : ℕ → ℝ) (δ : ℝ)
    (h_drift : ∀ k, V (k+1) + δ ≤ V k) :
    ∀ n, V n + n • δ ≤ V 0 := by
  intro n
  induction n with
  | zero =>
      simp
  | succ n ih =>
      have h' : (V (n+1) + δ) + n • δ ≤ V n + n • δ := add_le_add (h_drift n) le_rfl
      have eq : V (n+1) + (n + 1) • δ = (V (n+1) + δ) + n • δ := by rw [succ_nsmul, ← add_assoc, add_right_comm]
      rw [eq]
      exact le_trans h' ih

/-- Same bound stated as `V n ≤ V 0 - (n:ℝ)*δ`. -/
theorem algebraic_drift_bound (V : ℕ → ℝ) (δ : ℝ)
    (h_drift : ∀ k, V (k+1) ≤ V k - δ) (n : ℕ) :
    V n ≤ V 0 - (n : ℝ) * δ := by
  -- rewrite `V (k+1) ≤ V k - δ` into `V (k+1) + δ ≤ V k`
  have h' : ∀ k, V (k+1) + δ ≤ V k := by
    intro k; linarith [h_drift k]
  have hn : V n + n • δ ≤ V 0 := algebraic_drift_bound_nsmul (V := V) (δ := δ) h' n
  -- rearrange
  -- `n • δ = (n:ℝ) * δ` in `ℝ`
  have : (n • δ : ℝ) = (n : ℝ) * δ := by simp [nsmul_eq_mul]
  linarith [hn, this]

end Drift

/-!
## 3) “Ville-style” pointwise supermartingale bound
-/

section VillePointwise

variable {Ω : Type*} [MeasurableSpace Ω] (P : Measure Ω)
variable (M : ℕ → Ω → ℝ≥0∞)

/-- If `∫⁻ M(n+1) ≤ ∫⁻ M n`, then `∫⁻ M n ≤ ∫⁻ M 0`. -/
lemma lintegral_le_lintegral_zero
    (hmono : ∀ n, (∫⁻ ω, M (n+1) ω ∂P) ≤ (∫⁻ ω, M n ω ∂P)) :
    ∀ n, (∫⁻ ω, M n ω ∂P) ≤ (∫⁻ ω, M 0 ω ∂P) := by
  intro n
  induction n with
  | zero => simp
  | succ n ih => exact le_trans (hmono n) ih

/-- Pointwise Ville-style bound: `L * P{L ≤ M n} ≤ ∫⁻ M 0`. -/
theorem ville_martingale_bound_pointwise (hM : ∀ n, Measurable (M n))
    (hmono : ∀ n, (∫⁻ ω, M (n+1) ω ∂P) ≤ (∫⁻ ω, M n ω ∂P))
    (n : ℕ) (L : ℝ≥0∞) :
    L * P {ω | L ≤ M n ω} ≤ ∫⁻ ω, M 0 ω ∂P := by
  have hmarkov : L * P {ω | L ≤ M n ω} ≤ ∫⁻ ω, M n ω ∂P := by
    simpa using (MeasureTheory.mul_meas_ge_le_lintegral (hM n) L)
  exact le_trans hmarkov ((lintegral_le_lintegral_zero P M hmono) n)

end VillePointwise

/-!
## 4) Structural Ville's Maximal Inequality (Optional Stopping)
-/

section VilleMaximal

variable {Ω : Type*} [MeasurableSpace Ω] {μ : Measure Ω} [IsFiniteMeasure μ]
variable {ℱ : Filtration ℕ (‹MeasurableSpace Ω›)}
variable {M : ℕ → Ω → ℝ}

theorem ville_finite_horizon
    (h_super : Supermartingale M ℱ μ)
    (h_nonneg : ∀ n ω, 0 ≤ M n ω)
    (c : ℝ) (N : ℕ) :
    let A := {ω | ∃ k ∈ Set.Icc 0 N, c ≤ M k ω}
    (ENNReal.ofReal c) * μ A ≤ ENNReal.ofReal (∫ ω, M 0 ω ∂μ) := by
  intro A

  -- Work with the submartingale -M so we cleanly extract adaptedness properties
  have h_sub : Submartingale (-M) ℱ μ := h_super.neg
  have h_sm : ∀ k, StronglyMeasurable[ℱ k] (-M k) := h_sub.1
  have h_adapt_neg : Adapted ℱ (-M) := fun k => (h_sm k).measurable
  have h_meas_s : MeasurableSet (Set.Iic (-c)) := measurableSet_Iic

  have hA : MeasurableSet A := by
    have h_eq : A = ⋃ k : ℕ, if h : k ≤ N then {ω | c ≤ M k ω} else ∅ := by
      ext ω
      simp only [A, mem_setOf_eq, mem_iUnion, mem_Icc]
      constructor
      · rintro ⟨k, hk_Icc, hk_c⟩
        use k
        rw [dif_pos hk_Icc.2]
        exact hk_c
      · rintro ⟨k, hk⟩
        split_ifs at hk with h
        · exact ⟨k, ⟨Nat.zero_le k, h⟩, hk⟩
        · exact False.elim hk
    rw [h_eq]
    apply MeasurableSet.iUnion
    intro k
    split_ifs
    · have h_sm_k : StronglyMeasurable[ℱ k] (-M k) := h_sm k
      have h_sm_M : StronglyMeasurable[ℱ k] (M k) := by simpa using h_sm_k.neg
      have h1 : Measurable[ℱ k] (fun _ : Ω => c) := measurable_const
      have h2 : Measurable[ℱ k] (M k) := h_sm_M.measurable
      have h3 : MeasurableSet[ℱ k] {ω | c ≤ M k ω} := measurableSet_le h1 h2
      exact ℱ.le k _ h3
    · exact MeasurableSet.empty

  let τ_hit := fun ω ↦ hittingBtwn (-M) (Set.Iic (-c)) 0 N ω
  let τ : Ω → ℕ∞ := fun ω ↦ (τ_hit ω : ℕ∞)
  have hτ : IsStoppingTime ℱ τ := h_adapt_neg.isStoppingTime_hittingBtwn h_meas_s

  let τ_0 : Ω → ℕ∞ := fun _ ↦ 0
  have hτ_0 : IsStoppingTime ℱ τ_0 := isStoppingTime_const ℱ 0

  have hle_0_τ : τ_0 ≤ τ := fun ω ↦ bot_le
  have hbdd_τ : ∀ ω, τ ω ≤ (N : ℕ∞) := fun ω ↦ WithTop.coe_le_coe.mpr (hittingBtwn_le ω)

  have h_mono := Submartingale.expected_stoppedValue_mono h_sub hτ_0 hτ hle_0_τ hbdd_τ

  have h_neg_0 : ∫ x, stoppedValue (-M) τ_0 x ∂μ = - ∫ x, stoppedValue M τ_0 x ∂μ := by
    have : stoppedValue (-M) τ_0 = fun x ↦ - stoppedValue M τ_0 x := rfl
    rw [this, integral_neg]

  have h_neg_τ : ∫ x, stoppedValue (-M) τ x ∂μ = - ∫ x, stoppedValue M τ x ∂μ := by
    have : stoppedValue (-M) τ = fun x ↦ - stoppedValue M τ x := rfl
    rw [this, integral_neg]

  rw[h_neg_0, h_neg_τ] at h_mono
  have h_mono' : ∫ x, stoppedValue M τ x ∂μ ≤ ∫ x, stoppedValue M τ_0 x ∂μ := neg_le_neg_iff.mp h_mono

  have h_stop_0 : stoppedValue M τ_0 = M 0 := rfl
  rw [h_stop_0] at h_mono'

  have h_M_ge_c : ∀ ω ∈ A, c ≤ stoppedValue M τ ω := by
    intro ω hω
    have h_exists : ∃ j ∈ Set.Icc 0 N, (-M) j ω ∈ Set.Iic (-c) := by
      rcases hω with ⟨k, hk_Icc, hk_c⟩
      exact ⟨k, hk_Icc, neg_le_neg hk_c⟩
    exact neg_le_neg_iff.mp (stoppedValue_hittingBtwn_mem h_exists)

  have h_int_A : (ENNReal.ofReal c) * μ A ≤ ∫⁻ ω, A.indicator (fun ω ↦ ENNReal.ofReal (stoppedValue M τ ω)) ω ∂μ := by
    have h_c_ind : ∫⁻ ω, A.indicator (fun _ ↦ ENNReal.ofReal c) ω ∂μ = (ENNReal.ofReal c) * μ A := by
      rw [lintegral_indicator hA, lintegral_const]
      simp
    rw [← h_c_ind]
    apply lintegral_mono
    intro ω
    by_cases hω : ω ∈ A
    · simp [Set.indicator, hω]
      exact ENNReal.ofReal_le_ofReal (h_M_ge_c ω hω)
    · simp [Set.indicator, hω]

  have h_ind_le : ∫⁻ ω, A.indicator (fun ω ↦ ENNReal.ofReal (stoppedValue M τ ω)) ω ∂μ ≤ ∫⁻ ω, ENNReal.ofReal (stoppedValue M τ ω) ∂μ := by
    apply lintegral_mono
    intro ω
    by_cases hω : ω ∈ A
    · simp [Set.indicator, hω]
    · simp [Set.indicator, hω]

  have h_int_M : ∀ n, Integrable (M n) μ := fun n ↦ by
    have h1 : Integrable (-M n) μ := h_sub.2.2 n
    have h2 : Integrable (-(-M n)) μ := h1.neg
    have h_eq : -(-M n) = M n := neg_neg (M n)
    rw [h_eq] at h2
    exact h2

  have h_int_stop : Integrable (stoppedValue M τ) μ := integrable_stoppedValue ℕ hτ h_int_M hbdd_τ

  have h_ae_nn : 0 ≤ᵐ[μ] stoppedValue M τ := Eventually.of_forall (fun ω ↦ h_nonneg _ ω)
  have h_integral_le : ENNReal.ofReal (∫ ω, stoppedValue M τ ω ∂μ) ≤ ENNReal.ofReal (∫ ω, M 0 ω ∂μ) :=
    ENNReal.ofReal_le_ofReal h_mono'

  calc
    (ENNReal.ofReal c) * μ A
      ≤ ∫⁻ ω, A.indicator (fun ω ↦ ENNReal.ofReal (stoppedValue M τ ω)) ω ∂μ := h_int_A
    _ ≤ ∫⁻ ω, ENNReal.ofReal (stoppedValue M τ ω) ∂μ := h_ind_le
    _ = ENNReal.ofReal (∫ ω, stoppedValue M τ ω ∂μ) := by rw[MeasureTheory.ofReal_integral_eq_lintegral_ofReal h_int_stop h_ae_nn]
    _ ≤ ENNReal.ofReal (∫ ω, M 0 ω ∂μ) := h_integral_le

end VilleMaximal

end CoAI.Control
