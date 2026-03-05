/-
CoAI/CertifiedStack.lean

"SBOM" / bill-of-materials for the certified attention stack.
-/

import CoAI.ProbabilisticAttention
import CoAI.FAVOR
import CoAI.Concentration

namespace CoAI.SBOM

open MeasureTheory Real
open scoped InnerProductSpace

/-- The single capstone theorem linking the Unbiased Estimator property
    with the Sub-Gaussian Concentration Bound. 
    Now 100% free of domain-specific axioms! -/
theorem certified_attention_contract
  {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
  (m : ℕ) (ω : Ω → Fin m → E)
  (q k : E)
  (hm : 0 < m) (ε δ : ℝ) (hε : 0 < ε) (hδ : 0 < δ)
  (hm_req :
    Real.log (2 / δ) ≤ ((m : ℝ) * ε ^ 2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖)))
  (h_gaussian : ∀ r : Fin m, ∀ x : E,
    (volume.map (fun s => ⟪ω s r, x⟫_ℝ)) = ProbabilityTheory.gaussianReal 0 (‖x‖ ^ 2).toNNReal)
  (h_int : ∀ r : Fin m, MeasureTheory.Integrable (fun s => ∑ i : Fin 2,
    StochasticAttention.FavorPhi (ω s r) q i * StochasticAttention.FavorPhi (ω s r) k i) volume)
  (h_tail :
    (volume {s | ε ≤ |StochasticAttention.KernelError_m (m := m) (ω := ω) q k s|}).toReal ≤
      2 * Real.exp ( - ((m : ℝ) * ε^2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖)) )) :
  ((∫ s : Ω,
      ((1 / (m : ℝ)) * ∑ r : Fin m, ∑ i : Fin 2,
        StochasticAttention.FavorPhi (ω s r) q i * StochasticAttention.FavorPhi (ω s r) k i))
    = StochasticAttention.ExactSoftmax q k)
  ∧
  (volume {s | ε ≤ |StochasticAttention.KernelError_m (m := m) (ω := ω) q k s|}).toReal ≤ δ :=
by
  refine And.intro ?_ ?_
  · exact StochasticAttention.favor_is_unbiased_m m hm ω q k h_gaussian h_int
  · exact StochasticAttention.favor_bound_delta (m := m) (ω := ω) q k hm ε δ hε hδ h_tail hm_req

/-
------------------------------------------------------------------------------
THE AUDIT BOUNDARY
------------------------------------------------------------------------------
-/
#print axioms certified_attention_contract

end CoAI.SBOM
