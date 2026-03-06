import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.MeasureTheory.Measure.ProbabilityMeasure
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import CoAI.Concentration

open MeasureTheory Real
open scoped BigOperators

namespace StochasticAttention

variable {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]

-- finite key index type
variable {ι : Type*} [Fintype ι]

-- values live in a normed space; scalar case is V = ℝ
variable {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V]

variable (m : ℕ) (ω : Ω → Fin m → E)

-- Exact kernel
noncomputable def K (q k : E) : ℝ := ExactSoftmax q k

-- Approx kernel as exact + error
noncomputable def Khat (q k : E) (s : Ω) : ℝ :=
  K q k + KernelError_m (m := m) (ω := ω) q k s

-- Numerator/denominator and exact output
noncomputable def den (q : E) (keys : ι → E) : ℝ :=
  ∑ j, K (q := q) (keys j)

noncomputable def num (q : E) (keys : ι → E) (vals : ι → V) : V :=
  ∑ j, (K (q := q) (keys j)) • (vals j)

noncomputable def attn (q : E) (keys : ι → E) (vals : ι → V) : V :=
  (1 / den (q := q) keys) • num (q := q) keys vals

-- Approx numerator/denominator and output
noncomputable def denHat (q : E) (keys : ι → E) (s : Ω) : ℝ :=
  ∑ j, Khat (m := m) (ω := ω) (q := q) (keys j) s

noncomputable def numHat (q : E) (keys : ι → E) (vals : ι → V) (s : Ω) : V :=
  ∑ j, (Khat (m := m) (ω := ω) (q := q) (keys j) s) • (vals j)

noncomputable def attnHat (q : E) (keys : ι → E) (vals : ι → V) (s : Ω) : V :=
  (1 / denHat (m := m) (ω := ω) (q := q) keys s) • numHat (m := m) (ω := ω) (q := q) keys vals s

-- Event sets
def goodEvent (q : E) (keys : ι → E) (η : ℝ) : Set Ω :=
  {s | ∀ j, |KernelError_m (m := m) (ω := ω) q (keys j) s| < η}

def badEvent (q : E) (keys : ι → E) (η : ℝ) : Set Ω :=
  {s | ∃ j, η ≤ |KernelError_m (m := m) (ω := ω) q (keys j) s|}

section ToRealUnion

variable {Ω : Type*} [MeasurableSpace Ω]
variable (μ : Measure Ω) [IsFiniteMeasure μ]

lemma toReal_union_le (A B : Set Ω) :
    (μ (A ∪ B)).toReal ≤ (μ A).toReal + (μ B).toReal := by
  have hle : μ (A ∪ B) ≤ μ A + μ B := by
    simpa using (measure_union_le A B)
  have hA : μ A ≠ ⊤ := measure_ne_top μ A
  have hB : μ B ≠ ⊤ := measure_ne_top μ B
  have hTop : μ A + μ B ≠ ⊤ := ENNReal.add_ne_top.mpr ⟨hA, hB⟩
  have hmono : (μ (A ∪ B)).toReal ≤ (μ A + μ B).toReal :=
    ENNReal.toReal_mono hTop hle
  -- rewrite (μ A + μ B).toReal
  simpa [ENNReal.toReal_add hA hB] using hmono

end ToRealUnion

section ToRealFinsetUnion

variable {Ω : Type*} [MeasurableSpace Ω]
variable (μ : Measure Ω) [IsFiniteMeasure μ]
variable {ι : Type*}

lemma toReal_iUnion_finset_le_sum (s : Finset ι) (A : ι → Set Ω) :
    (μ (⋃ i ∈ s, A i)).toReal ≤ ∑ i ∈ s, (μ (A i)).toReal := by
  classical
  refine Finset.induction_on s ?base ?step
  · -- s = ∅
    simp
  · intro a s ha hs
    -- rewrite the union over insert
    have hset : (⋃ i ∈ insert a s, A i) = A a ∪ ⋃ i ∈ s, A i := by
      ext ω
      simp
    calc
      (μ (⋃ i ∈ insert a s, A i)).toReal
          = (μ (A a ∪ ⋃ i ∈ s, A i)).toReal := by rw [hset]
      _   ≤ (μ (A a)).toReal + (μ (⋃ i ∈ s, A i)).toReal := by
              simpa using toReal_union_le (μ := μ) (A := A a) (B := ⋃ i ∈ s, A i)
      _   ≤ (μ (A a)).toReal + ∑ i ∈ s, (μ (A i)).toReal := by
              linarith [hs]
      _   = ∑ i ∈ insert a s, (μ (A i)).toReal := by
              rw [Finset.sum_insert ha]

end ToRealFinsetUnion

section RatioStability

variable {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V]

/-- Helper: derive a lower bound on `DenHat` from `|DenHat - Den| ≤ γ/2` and `γ ≤ Den`. -/
lemma denHat_lower_of_abs_sub
    (Den DenHat γ : ℝ) (hγ : 0 < γ) (hDen : γ ≤ Den) (hclose : |DenHat - Den| ≤ γ/2) :
    γ/2 ≤ DenHat := by
  -- Use `abs_sub_le_iff` to get two inequalities.
  have h := (abs_sub_le_iff).1 (by simpa using hclose)
  -- h : Den - γ/2 ≤ DenHat ∧ DenHat ≤ Den + γ/2
  -- Combine γ ≤ Den with Den - γ/2 ≤ DenHat to get γ/2 ≤ DenHat.
  linarith [hDen, h.1]

/-- Helper: bound `|1/DenHat|` by `2/γ` given `γ/2 ≤ DenHat` and `γ>0`. -/
lemma abs_inv_le_two_div
    (DenHat γ : ℝ) (hγ : 0 < γ) (hDenHat : γ/2 ≤ DenHat) :
    |(1 / DenHat)| ≤ 2/γ := by
  have hγ2 : 0 < γ/2 := by nlinarith [hγ]
  have hDenHatPos : 0 < DenHat := lt_of_lt_of_le hγ2 hDenHat

  have hinv : (1 / DenHat) ≤ (1 / (γ/2)) := by
    -- 0 < γ/2 and γ/2 ≤ DenHat ⇒ 1/DenHat ≤ 1/(γ/2)
    exact one_div_le_one_div_of_le hγ2 hDenHat

  have hdiv : (1 / (γ/2 : ℝ)) = (2/γ) := by
    have hγ0 : (γ : ℝ) ≠ 0 := ne_of_gt hγ
    field_simp [hγ0]
    try ring

  have hbound : (1 / DenHat) ≤ 2/γ := by
    calc
      (1 / DenHat) ≤ (1 / (γ/2)) := hinv
      _ = 2/γ := hdiv

  have hposInv : 0 < (1 / DenHat) := by positivity

  rw [abs_of_pos hposInv]
  exact hbound

/-- Helper: bound `|1/DenHat - 1/Den|` by `(2/γ^2)*|DenHat - Den|`. -/
lemma abs_inv_sub_inv_le
    (Den DenHat γ : ℝ) (hγ : 0 < γ) (hDen : γ ≤ Den) (hDenHat : γ/2 ≤ DenHat) :
    |(1/DenHat) - (1/Den)| ≤ (2/γ^2) * |DenHat - Den| := by
  have hγ2 : 0 < γ/2 := by nlinarith [hγ]
  have hDenPos : 0 < Den := lt_of_lt_of_le hγ hDen
  have hDenHatPos : 0 < DenHat := lt_of_lt_of_le hγ2 hDenHat
  have hprodPos : 0 < DenHat * Den := mul_pos hDenHatPos hDenPos

  -- Lower bound DenHat*Den ≥ (γ/2)*γ = γ^2/2
  have hmul : (γ/2) * γ ≤ DenHat * Den := by
    have hγnonneg : 0 ≤ γ := le_of_lt hγ
    have hDenHatNonneg : 0 ≤ DenHat := le_trans (le_of_lt hγ2) hDenHat
    exact mul_le_mul hDenHat hDen hγnonneg hDenHatNonneg

  have hprodLower : (γ^2) / 2 ≤ DenHat * Den := by
    have hEq : (γ/2) * γ = (γ^2)/2 := by nlinarith
    simpa [hEq] using hmul

  have hγ2sq : 0 < (γ^2) / 2 := by nlinarith [hγ]

  -- Invert the product lower bound to get 1/(DenHat*Den) ≤ 1/(γ^2/2)
  have hinv : (1 / (DenHat * Den)) ≤ (1 / ((γ^2) / 2)) := by
    exact one_div_le_one_div_of_le hγ2sq hprodLower

  have hdiv : (1 / ((γ^2) / 2 : ℝ)) = (2 / γ^2) := by
    have hγ0 : (γ : ℝ) ≠ 0 := ne_of_gt hγ
    have hγ2ne : (γ^2 : ℝ) ≠ 0 := by
      -- γ ≠ 0 ⇒ γ^2 ≠ 0
      exact pow_ne_zero 2 hγ0
    field_simp [hγ2ne]
    try ring

  have hinv2 : (1 / (DenHat * Den)) ≤ (2 / γ^2) := by
    simpa [hdiv] using hinv

  -- Identity: 1/DenHat - 1/Den = (Den - DenHat)/(DenHat*Den)
  have hdiff : (1/DenHat) - (1/Den) = (Den - DenHat) / (DenHat * Den) := by
    have hd1 : DenHat ≠ 0 := ne_of_gt hDenHatPos
    have hd2 : Den ≠ 0 := ne_of_gt hDenPos
    field_simp [hd1, hd2]
    try ring

  calc
    |(1/DenHat) - (1/Den)|
        = |(Den - DenHat) / (DenHat * Den)| := by rw [hdiff]
    _   = |Den - DenHat| / |DenHat * Den| := by simp [abs_div]
    _   = |DenHat - Den| / (DenHat * Den) := by
            have habsden : |DenHat * Den| = DenHat * Den := abs_of_pos hprodPos
            simp [abs_sub_comm, habsden]
    _   = |DenHat - Den| * (1 / (DenHat * Den)) := by
            simp [div_eq_mul_inv]
    _   ≤ |DenHat - Den| * (2 / γ^2) := by
            have hnonneg : 0 ≤ |DenHat - Den| := by positivity
            exact mul_le_mul_of_nonneg_left hinv2 hnonneg
    _   = (2 / γ^2) * |DenHat - Den| := by
            rw [mul_comm]

/-- Main deterministic ratio-stability bound (Track B core). -/
theorem ratio_stability_bound
    (Num NumHat : V) (Den DenHat γ : ℝ)
    (hγ : 0 < γ) (hDen : γ ≤ Den) (hclose : |DenHat - Den| ≤ γ/2) :
    ‖(1 / DenHat) • NumHat - (1 / Den) • Num‖
      ≤ (2/γ) * ‖NumHat - Num‖ + (2/γ^2) * ‖Num‖ * |DenHat - Den| := by
  -- Step 1: lower bound DenHat
  have hDenHat : γ/2 ≤ DenHat := denHat_lower_of_abs_sub Den DenHat γ hγ hDen hclose

  -- Step 2: algebraic decomposition
  have hdecomp :
      (1 / DenHat) • NumHat - (1 / Den) • Num
        = (1 / DenHat) • (NumHat - Num) + ((1 / DenHat) - (1 / Den)) • Num := by
    rw [smul_sub, sub_smul]
    abel

  -- Step 3: take norms and apply triangle inequality
  calc
    ‖(1 / DenHat) • NumHat - (1 / Den) • Num‖
        = ‖(1 / DenHat) • (NumHat - Num) + ((1 / DenHat) - (1 / Den)) • Num‖ := by
            rw [hdecomp]
    _   ≤ ‖(1 / DenHat) • (NumHat - Num)‖ + ‖((1 / DenHat) - (1 / Den)) • Num‖ := by
            exact norm_add_le _ _
    _   = ‖(1 / DenHat : ℝ)‖ * ‖NumHat - Num‖ + ‖((1 / DenHat) - (1 / Den) : ℝ)‖ * ‖Num‖ := by
            simp only [norm_smul]
    _   = |(1 / DenHat)| * ‖NumHat - Num‖ + |(1 / DenHat - 1 / Den)| * ‖Num‖ := by
            simp only [Real.norm_eq_abs]
    _   ≤ (2/γ) * ‖NumHat - Num‖ + ((2/γ^2) * |DenHat - Den|) * ‖Num‖ := by
            have h1 : |(1 / DenHat)| ≤ 2/γ := abs_inv_le_two_div DenHat γ hγ hDenHat
            have h2 : |(1/DenHat) - (1/Den)| ≤ (2/γ^2) * |DenHat - Den| :=
              abs_inv_sub_inv_le Den DenHat γ hγ hDen hDenHat
            have hn1 : 0 ≤ ‖NumHat - Num‖ := by positivity
            have hn2 : 0 ≤ ‖Num‖ := by positivity
            exact add_le_add
              (mul_le_mul_of_nonneg_right h1 hn1)
              (mul_le_mul_of_nonneg_right h2 hn2)
    _   = (2/γ) * ‖NumHat - Num‖ + (2/γ^2) * ‖Num‖ * |DenHat - Den| := by
            ring_nf

end RatioStability

section DeterministicHook

variable {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
variable {ι : Type*} [Fintype ι]
variable {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V]
variable (m : ℕ) (ω : Ω → Fin m → E)

/--
Deterministic hook: on `goodEvent`, if you have the standard numerator and denominator
perturbation bounds, then ratio stability yields the final attention-output bound.
-/
theorem goodEvent_implies_output_error_bound
    (q : E) (keys : ι → E) (vals : ι → V)
    (η γ : ℝ) (hη : 0 ≤ η) (hγ : 0 < γ)
    (hDen : γ ≤ den (q := q) keys)
    (hηsmall : (Fintype.card ι : ℝ) * η ≤ γ/2)
    {s : Ω} (hs : s ∈ goodEvent (m := m) (ω := ω) q keys η)
    (hNumErr :
      ‖numHat (m := m) (ω := ω) (q := q) keys vals s - num (q := q) keys vals‖
        ≤ η * (∑ j, ‖vals j‖))
    (hDenErr :
      |denHat (m := m) (ω := ω) (q := q) keys s - den (q := q) keys|
        ≤ (Fintype.card ι : ℝ) * η) :
    ‖attnHat (m := m) (ω := ω) (q := q) keys vals s - attn (q := q) keys vals‖
      ≤ (2/γ) * (η * (∑ j, ‖vals j‖))
        + (2/γ^2) * ‖num (q := q) keys vals‖ * ((Fintype.card ι : ℝ) * η) := by
  let Den : ℝ := den (q := q) keys
  let DenHat : ℝ := denHat (m := m) (ω := ω) (q := q) keys s
  let Num : V := num (q := q) keys vals
  let NumHat : V := numHat (m := m) (ω := ω) (q := q) keys vals s

  have hclose : |DenHat - Den| ≤ γ/2 := by
    have : |DenHat - Den| = |denHat (m := m) (ω := ω) (q := q) keys s - den (q := q) keys| := by rfl
    exact le_trans (by simpa [DenHat, Den] using hDenErr) hηsmall

  have hratio :
      ‖(1 / DenHat) • NumHat - (1 / Den) • Num‖
        ≤ (2/γ) * ‖NumHat - Num‖ + (2/γ^2) * ‖Num‖ * |DenHat - Den| := by
    simpa [DenHat, Den, NumHat, Num] using
      (ratio_stability_bound (Num := Num) (NumHat := NumHat)
        (Den := Den) (DenHat := DenHat) (γ := γ) hγ (by simpa [Den] using hDen) hclose)

  have herr_id :
      attnHat (m := m) (ω := ω) (q := q) keys vals s - attn (q := q) keys vals
        = (1 / DenHat) • NumHat - (1 / Den) • Num := by rfl

  have hNumErr' : ‖NumHat - Num‖ ≤ η * (∑ j, ‖vals j‖) := by simpa [NumHat, Num] using hNumErr
  have hDenErr' : |DenHat - Den| ≤ (Fintype.card ι : ℝ) * η := by simpa [DenHat, Den] using hDenErr

  have hconst1 : 0 ≤ (2/γ) := le_of_lt (by positivity)
  have hconst2 : 0 ≤ (2/γ^2) * ‖Num‖ := mul_nonneg (by positivity) (by positivity)

  have hterm1 :
      (2/γ) * ‖NumHat - Num‖ ≤ (2/γ) * (η * (∑ j, ‖vals j‖)) :=
    mul_le_mul_of_nonneg_left hNumErr' hconst1

  have hterm2 :
      (2/γ^2) * ‖Num‖ * |DenHat - Den|
        ≤ (2/γ^2) * ‖Num‖ * ((Fintype.card ι : ℝ) * η) :=
    mul_le_mul_of_nonneg_left hDenErr' hconst2

  calc
    ‖attnHat (m := m) (ω := ω) (q := q) keys vals s - attn (q := q) keys vals‖
        = ‖(1 / DenHat) • NumHat - (1 / Den) • Num‖ := by simpa [herr_id]
    _   ≤ (2/γ) * ‖NumHat - Num‖ + (2/γ^2) * ‖Num‖ * |DenHat - Den| := hratio
    _   ≤ (2/γ) * (η * (∑ j, ‖vals j‖))
          + (2/γ^2) * ‖Num‖ * ((Fintype.card ι : ℝ) * η) := by exact add_le_add hterm1 hterm2
    _   = (2/γ) * (η * (∑ j, ‖vals j‖))
          + (2/γ^2) * ‖num (q := q) keys vals‖ * ((Fintype.card ι : ℝ) * η) := by rfl

end DeterministicHook

section Phase3

set_option linter.unusedSectionVars false

variable {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
variable {ι : Type*} [Fintype ι]
variable (m : ℕ) (ω : Ω → Fin m → E)

/-- Phase 2a: deterministic containment `badEvent ⊆ goodEventᶜ`. -/
theorem badEvent_subset_goodEvent_compl
    (q : E) (keys : ι → E) (η : ℝ) :
    badEvent (m := m) (ω := ω) q keys η ⊆
      (goodEvent (m := m) (ω := ω) q keys η)ᶜ := by
  intro s hs hgood
  rcases hs with ⟨j, hj⟩
  have hjgood := hgood j
  exact (not_lt_of_ge hj) hjgood

/-- Phase 2a (stronger): `goodEventᶜ = badEvent` for your aligned definitions. -/
theorem goodEvent_compl_eq_badEvent
    (q : E) (keys : ι → E) (η : ℝ) :
    (goodEvent (m := m) (ω := ω) q keys η)ᶜ =
      badEvent (m := m) (ω := ω) q keys η := by
  classical
  ext s
  simp [goodEvent, badEvent, not_forall, not_lt]

/-- Helper: the per-key tail set used in union bounds. -/
def tailSet (q : E) (keys : ι → E) (η : ℝ) (j : ι) : Set Ω :=
  {s | η ≤ |KernelError_m (m := m) (ω := ω) q (keys j) s|}

-- We use the fact that probability measures are finite measures
local instance (μ : Measure Ω) [IsProbabilityMeasure μ] : IsFiniteMeasure μ := by
  infer_instance

/-- Phase 2b: probability bound on `goodEventᶜ` using a finite union bound. -/
theorem prob_goodEvent_compl_le_card_mul
    (q : E) (keys : ι → E) (η δ0 : ℝ)
    (h_tail : ∀ j : ι,
      (volume {s | η ≤ |KernelError_m (m := m) (ω := ω) q (keys j) s|}).toReal ≤ δ0) :
    (volume (goodEvent (m := m) (ω := ω) q keys η)ᶜ).toReal ≤
      (Fintype.card ι : ℝ) * δ0 := by
  classical

  -- rewrite goodEventᶜ as badEvent
  have hcompl :
      (goodEvent (m := m) (ω := ω) q keys η)ᶜ =
        badEvent (m := m) (ω := ω) q keys η :=
    goodEvent_compl_eq_badEvent (m := m) (ω := ω) (q := q) (keys := keys) (η := η)

  -- express badEvent as a finite union over `Finset.univ`
  let A : ι → Set Ω := fun j => tailSet (m := m) (ω := ω) q keys η j

  have hunion_repr :
      badEvent (m := m) (ω := ω) q keys η =
        ⋃ j ∈ (Finset.univ : Finset ι), A j := by
    ext s
    simp [badEvent, A, tailSet]

  -- Apply your `.toReal` finset union bound lemma
  have hunion_le :
      (volume (⋃ j ∈ (Finset.univ : Finset ι), A j)).toReal ≤
        ∑ j ∈ (Finset.univ : Finset ι), (volume (A j)).toReal := by
    simpa using
      (toReal_iUnion_finset_le_sum (μ := volume)
        (s := (Finset.univ : Finset ι)) (A := A))

  -- Bound each summand by δ0 then compute the sum = card*δ0
  have hsum_le :
      (∑ j ∈ (Finset.univ : Finset ι), (volume (A j)).toReal)
        ≤ (Fintype.card ι : ℝ) * δ0 := by
    have h_each : ∀ j : ι, (volume (A j)).toReal ≤ δ0 := by
      intro j
      simpa [A, tailSet] using h_tail j

    calc
      (∑ j ∈ (Finset.univ : Finset ι), (volume (A j)).toReal)
          ≤ ∑ j ∈ (Finset.univ : Finset ι), δ0 := by
              exact Finset.sum_le_sum (by intro j hj; exact h_each j)
      _   = (Fintype.card ι : ℝ) * δ0 := by
              simp [Finset.card_univ]

  -- Put it together
  calc
    (volume (goodEvent (m := m) (ω := ω) q keys η)ᶜ).toReal
        = (volume (badEvent (m := m) (ω := ω) q keys η)).toReal := by
            simp [hcompl]
    _   = (volume (⋃ j ∈ (Finset.univ : Finset ι), A j)).toReal := by
            simp [hunion_repr]
    _   ≤ ∑ j ∈ (Finset.univ : Finset ι), (volume (A j)).toReal := hunion_le
    _   ≤ (Fintype.card ι : ℝ) * δ0 := hsum_le

/-- Phase 2b (glue): same probability bound, but stated directly for `badEvent`. -/
theorem prob_badEvent_le_card_mul
    (q : E) (keys : ι → E) (η δ0 : ℝ)
    (h_tail : ∀ j : ι,
      (volume {s | η ≤ |KernelError_m (m := m) (ω := ω) q (keys j) s|}).toReal ≤ δ0) :
    (volume (badEvent (m := m) (ω := ω) q keys η)).toReal ≤
      (Fintype.card ι : ℝ) * δ0 := by
  have hcompl :=
    goodEvent_compl_eq_badEvent (m := m) (ω := ω) (q := q) (keys := keys) (η := η)
  have h :=
    prob_goodEvent_compl_le_card_mul (m := m) (ω := ω) (q := q) (keys := keys)
      (η := η) (δ0 := δ0) h_tail
  simpa [hcompl] using h

/-- Phase 3 capstone (probabilistic glue):
if on `goodEvent` the output error is bounded by `τ`, then the strict exceedance
event `{τ < ‖err(s)‖}` is contained in `goodEventᶜ` and hence has probability
at most `card * δ0`. -/
theorem certified_normalized_attention_contract_strict
    {V : Type*} [NormedAddCommGroup V] [NormedSpace ℝ V]
    (q : E) (keys : ι → E) (η δ0 τ : ℝ)
    (err : Ω → V)
    (h_det : ∀ s, s ∈ goodEvent (m := m) (ω := ω) q keys η → ‖err s‖ ≤ τ)
    (h_tail : ∀ j : ι,
      (volume {s | η ≤ |KernelError_m (m := m) (ω := ω) q (keys j) s|}).toReal ≤ δ0) :
    (volume {s | τ < ‖err s‖}).toReal ≤ (Fintype.card ι : ℝ) * δ0 := by
  -- 1) show strict exceedance event is subset of goodEventᶜ
  have hsubset : {s | τ < ‖err s‖} ⊆ (goodEvent (m := m) (ω := ω) q keys η)ᶜ := by
    intro s hs hgood
    have hle : ‖err s‖ ≤ τ := h_det s hgood
    exact (not_lt_of_ge hle) hs

  -- 2) monotonicity of measure + toReal monotonicity
  have hμ : volume {s | τ < ‖err s‖} ≤ volume (goodEvent (m := m) (ω := ω) q keys η)ᶜ :=
    measure_mono hsubset
  have hA : volume (goodEvent (m := m) (ω := ω) q keys η)ᶜ ≠ ⊤ := measure_ne_top _ _
  have hμ_toReal :
      (volume {s | τ < ‖err s‖}).toReal ≤
        (volume (goodEvent (m := m) (ω := ω) q keys η)ᶜ).toReal :=
    ENNReal.toReal_mono hA hμ

  -- 3) apply union-bound probability estimate for goodEventᶜ
  have hgood :
      (volume (goodEvent (m := m) (ω := ω) q keys η)ᶜ).toReal ≤ (Fintype.card ι : ℝ) * δ0 :=
    prob_goodEvent_compl_le_card_mul (m := m) (ω := ω) (q := q) (keys := keys)
      (η := η) (δ0 := δ0) h_tail

  exact le_trans hμ_toReal hgood

end Phase3

end StochasticAttention
