import Mathlib.Probability.ProbabilityMassFunction.Basic
import Mathlib.Topology.Instances.ENNReal.Lemmas

lemma pmf_summable_toReal {α : Type*} (p : PMF α) : Summable (fun x => (p x).toReal) := by
  have h1 : HasSum p.1 1 := p.2
  have h_tsum : ∑' x, p.1 x = 1 := h1.tsum_eq
  have h_ne_top : ∑' x, p.1 x ≠ ⊤ := by
    rw [h_tsum]
    exact ENNReal.one_ne_top
  exact ENNReal.summable_toReal h_ne_top
