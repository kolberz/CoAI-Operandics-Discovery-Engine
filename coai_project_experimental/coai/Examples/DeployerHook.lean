import CoAI.CertifiedStack
import Mathlib.Tactic.Positivity

open MeasureTheory ProbabilityTheory Real
open scoped BigOperators InnerProductSpace

namespace CoAI.Examples

variable {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]

/-- Example showing how a deployer constructs the integration contract.
By providing the specific projection measure and random feature definition,
they supply the MGF proof, and the stack executes the exact mathematical bridge. -/
theorem certified_deployer_hook
    (m : ℕ) (hm : 0 < m) (ω : Ω → Fin m → E)
    (q k : E) (ε δ : ℝ) (hε : 0 < ε) (hδ : 0 < δ)
    (hm_req : Real.log (2 / δ) ≤ ((m : ℝ) * ε^2) / (2 * Real.exp (2 * ‖q‖ * ‖k‖)))
    (h_gaussian : ∀ r : Fin m, ∀ x : E,
      (volume.map (fun s => ⟪ω s r, x⟫_ℝ)) = gaussianReal 0 (‖x‖ ^ 2).toNNReal)
    (h_int : ∀ r : Fin m, Integrable (fun s => ∑ i : Fin 2,
      StochasticAttention.FavorPhi (ω s r) q i * StochasticAttention.FavorPhi (ω s r) k i) volume)
    (hmgf : HasSubgaussianMGF (fun s => StochasticAttention.KernelError_m (m := m) (ω := ω) q k s)
      ⟨Real.exp (2 * ‖q‖ * ‖k‖) / (m : ℝ), by positivity⟩ volume) :
    ((∫ s : Ω,
        ((1 / (m : ℝ)) * ∑ r : Fin m, ∑ i : Fin 2,
          StochasticAttention.FavorPhi (ω s r) q i * StochasticAttention.FavorPhi (ω s r) k i))
      = StochasticAttention.ExactSoftmax q k)
    ∧
    (volume {s | ε ≤ |StochasticAttention.KernelError_m (m := m) (ω := ω) q k s|}).toReal ≤ δ := by

  -- The deployer extracts the exact variance proxy parameter.
  let c : NNReal := ⟨Real.exp (2 * ‖q‖ * ‖k‖) / (m : ℝ), by positivity⟩
  have hc : (c : ℝ) = Real.exp (2 * ‖q‖ * ‖k‖) / (m : ℝ) := rfl

  -- The deployer utilizes the stack's verified integration theorem to close the `h_tail` requirement.
  have h_tail :=
    StochasticAttention.kernelError_h_tail_of_mgf_exp_norm_div_m
      (m := m) (ω := ω) q k ε hε c hmgf hc

  -- The exact capstone contract is satisfied seamlessly.
  exact CoAI.SBOM.certified_attention_contract (m := m) (ω := ω) q k hm ε δ hε hδ hm_req h_gaussian h_int h_tail

end CoAI.Examples
