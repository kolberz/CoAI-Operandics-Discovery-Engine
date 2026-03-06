import CoAI.Substrate
import Mathlib.Probability.ProbabilityMassFunction.Basic
import Mathlib.Probability.ProbabilityMassFunction.Monad
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.Topology.Instances.ENNReal.Lemmas
import Mathlib.Topology.Algebra.InfiniteSum.ENNReal
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

noncomputable section

namespace CoAI.Composition

  structure Contract (State : Type*) where
    Assumption : State → Prop
    Guarantee  : State → Prop
    epsilon    : ℝ
    eps_nonneg : 0 ≤ epsilon

  structure Module (State : Type*) [MeasurableSpace State] [Countable State] where
    contract : Contract State
    kernel   : State → PMF State
    sound    : ∀ s, contract.Assumption s → 
      (kernel s).toOuterMeasure {s' | ¬contract.Guarantee s'} ≤ 
        ENNReal.ofReal contract.epsilon

  theorem seq_composition_risk_bound 
      {S : Type*} [MeasurableSpace S] [Countable S]
      (M1 M2 : Module S) 
      (h_compat : ∀ s, M1.contract.Guarantee s → M2.contract.Assumption s)
      (s : S) (hs : M1.contract.Assumption s) :
      ((M1.kernel s) >>= M2.kernel).toOuterMeasure {s' | ¬M2.contract.Guarantee s'} ≤ 
        ENNReal.ofReal (M1.contract.epsilon + M2.contract.epsilon) := by
    
    set B := {s' : S | ¬M2.contract.Guarantee s'}
    set p := M1.kernel s
    set f := M2.kernel
    set ε₁ := M1.contract.epsilon
    set ε₂ := M2.contract.epsilon

    -- 1. Outer measure over PMF.bind (CLOSED)
    have bind_expand : (p >>= f).toOuterMeasure B = ∑' mid, p mid * (f mid).toOuterMeasure B := 
      PMF.toOuterMeasure_bind_apply p f B

    -- 2. Probability bounds (CLOSED)
    have prob_le_one : ∀ (q : PMF S) (T : Set S), q.toOuterMeasure T ≤ 1 := by
      intro q T
      calc q.toOuterMeasure T 
        _ ≤ q.toOuterMeasure Set.univ := MeasureTheory.OuterMeasure.mono _ (Set.subset_univ T)
        _ = ∑' x, q x := by rw [PMF.toOuterMeasure_apply]; simp
        _ = 1 := PMF.tsum_coe q

    -- 3. Pointwise bounded indicator function (CLOSED)
    have h_pw : ∀ mid, p mid * (f mid).toOuterMeasure B ≤ p mid * ENNReal.ofReal ε₂ + Set.indicator {m | ¬M1.contract.Guarantee m} (fun m => p m) mid := by
      intro mid
      by_cases hg : M1.contract.Guarantee mid
      · simp [Set.indicator, hg]
        gcongr
        exact M2.sound mid (h_compat mid hg)
      · simp [Set.indicator, hg]
        calc p mid * (f mid).toOuterMeasure B 
          _ ≤ p mid * 1 := by gcongr; exact prob_le_one _ B
          _ = p mid := mul_one _
          _ ≤ p mid * ENNReal.ofReal ε₂ + p mid := le_add_left (le_refl _)

    -- 4. Assembly and resolution (CLOSED)
    rw [bind_expand]
    apply (ENNReal.tsum_le_tsum h_pw).trans
    rw [ENNReal.tsum_add, ENNReal.tsum_mul_right, PMF.tsum_coe p, one_mul]
    have h_final : ENNReal.ofReal ε₂ + ∑' mid, Set.indicator {m | ¬M1.contract.Guarantee m} (fun m => p m) mid ≤ ENNReal.ofReal (ε₁ + ε₂) := by
      rw [ENNReal.ofReal_add M1.contract.eps_nonneg M2.contract.eps_nonneg, add_comm, ← PMF.toOuterMeasure_apply]
      exact add_le_add_left (M1.sound s hs) _
    exact h_final

end CoAI.Composition
