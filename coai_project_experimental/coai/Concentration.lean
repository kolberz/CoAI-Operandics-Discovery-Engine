import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.Tactic.Positivity
import CoAI.FAVOR
import CoAI.FavorSubGaussian
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

open ProbabilityTheory

/-- (1) MGF ⇒ canonical two-sided exponential tail envelope for `KernelError_m`,
in the exact `.toReal` measure form. -/
theorem kernelError_tail_envelope_of_mgf
    {c : NNReal} (q k : E) (ε : ℝ) (hε : 0 < ε)
    (hmgf :
      HasSubgaussianMGF
        (fun s => KernelError_m (m := m) (ω := ω) q k s) c volume) :
    (volume {s | ε ≤ |KernelError_m (m := m) (ω := ω) q k s|}).toReal ≤
      2 * Real.exp (-ε^2 / (2 * (c : ℝ))) := by
  have h0 : 0 ≤ ε := le_of_lt hε
  -- abs_tail gives μ.real; unfold μ.real = (μ _).toReal via simp [Measure.real]
  simpa [Measure.real] using
    (CoAI.SubGaussian.abs_tail (μ := volume)
      (X := fun s => KernelError_m (m := m) (ω := ω) q k s)
      (c := c) hmgf ε h0)


/-- (2) MGF ⇒ the exact `h_tail` binder shape used by `CertifiedStack.lean`,
assuming `(c:ℝ) = exp(2‖q‖‖k‖)/m`. -/
theorem kernelError_h_tail_of_mgf_exp_norm_div_m
    (q k : E) (ε : ℝ) (hε : 0 < ε)
    (c : NNReal)
    (hmgf :
      HasSubgaussianMGF
        (fun s => KernelError_m (m := m) (ω := ω) q k s) c volume)
    (hc : (c : ℝ) = Real.exp (2 * ‖q‖ * ‖k‖) / (m : ℝ)) :
    (volume {s | ε ≤ |KernelError_m (m := m) (ω := ω) q k s|}).toReal ≤
      2 * Real.exp ( - ((m : ℝ) * ε^2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖)) ) := by
  -- Start from generic envelope (RHS = 2 * exp(-ε^2/(2*c)))
  have henv :=
    kernelError_tail_envelope_of_mgf (m := m) (ω := ω) (q := q) (k := k)
      (ε := ε) hε (c := c) hmgf

  -- Abbreviations for readability
  let A : ℝ := Real.exp (2 * ‖q‖ * ‖k‖)
  let M : ℝ := (m : ℝ)

  have hc' : (c : ℝ) = A / M := by
    -- expands A and M into the hc statement
    simpa [A, M] using hc

  -- Rewrite the exponent exactly, staying in "fraction" form (no simp normalization to invs).
  have hexp :
      (-ε^2) / (2 * (c : ℝ)) =
        - ((m : ℝ) * ε^2) / (2 * A) := by
    -- rewrite c using hc'
    -- goal becomes: (-ε^2)/(2*(A/M)) = -(M*ε^2)/(2*A)
    -- then unfold M = (m:ℝ)
    rw [hc']
    -- Denominator rewrite: 2 * (A / M) = (2 * A) / M
    have hdenom : 2 * (A / M) = (2 * A) / M := by
      -- `mul_div_assoc` has form (2*A)/M = 2*(A/M)
      simpa using (mul_div_assoc (2 : ℝ) A M).symm
    -- Now compute by dividing by a quotient
    calc
      (-ε^2) / (2 * (A / M))
          = (-ε^2) / ((2 * A) / M) := by simpa [hdenom]
      _   = (-ε^2) * M / (2 * A) := by
              -- a / (b / c) = a * c / b
              simpa using (div_div_eq_mul_div (-ε^2) (2 * A) M)
      _   = - (M * ε^2) / (2 * A) := by
              -- normalize (-ε^2)*M into -(M*ε^2)
              -- no big simp-set; do it in two tiny simp steps
              -- (-ε^2) * M = -(ε^2 * M) and ε^2 * M = M * ε^2
              have h1 : (-ε^2) * M = -(ε^2 * M) := by
                simpa using (neg_mul (ε^2) M)
              have h2 : ε^2 * M = M * ε^2 := by
                simpa [mul_comm] using (mul_comm (ε^2) M)
              -- apply both rewrites
              -- (-(ε^2*M))/(2*A) = -(M*ε^2)/(2*A)
              -- Use `rw` to avoid simp normalizing divisions.
              rw [h1]
              congr 1
              rw [h2]
      _   = - ((m : ℝ) * ε^2) / (2 * A) := by
              -- unfold M
              simpa [M]
  -- Turn exponent equality into equality of the full RHS via congrArg.
  have hrhs :
      2 * Real.exp (-ε^2 / (2 * (c : ℝ))) =
        2 * Real.exp ( - ((m : ℝ) * ε^2) / (2 * A) ) := by
    -- Note: -ε^2/(...) parses as (-ε^2)/(...), so `hexp` applies directly after rewriting.
    have hexp' :
        (-ε^2) / (2 * (c : ℝ)) =
          - ((m : ℝ) * ε^2) / (2 * A) := hexp
    simpa using congrArg (fun t => 2 * Real.exp t) hexp'

  -- Rewrite RHS of `henv` using hrhs, then unfold A to match CertifiedStack's exact string.
  have : (volume {s | ε ≤ |KernelError_m (m := m) (ω := ω) q k s|}).toReal ≤
        2 * Real.exp ( - ((m : ℝ) * ε^2) / (2 * A) ) := by
    -- rewrite the RHS of henv
    simpa [hrhs] using henv

  -- unfold A = exp(2‖q‖‖k‖)
  simpa [A] using this

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
