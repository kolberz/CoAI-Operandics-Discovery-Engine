import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

namespace CoAI.Economics

  structure EconomicsParams where
    lambda_R : ℝ
    lambda_C : ℝ
    lambda_v : ℝ

  class EconomicEnvironment (State Action : Type*) where
    ExpectedUtility    : State → Action → ℝ
    ExpectedRisk       : State → Action → ℝ
    TotalCostOwnership : Action → ℝ

  class EfficientMarket (State Action : Type*) extends EconomicEnvironment State Action where
    IsEquilibrium : State → Action → EconomicsParams → Prop
    no_arbitrage : ∀ s a p, IsEquilibrium s a p →
      ExpectedUtility s a - p.lambda_R * ExpectedRisk s a ≤ 
        (p.lambda_v + p.lambda_C) * TotalCostOwnership a

  def ValueObjective {S A : Type*} [E : EconomicEnvironment S A] 
      (s : S) (a : A) (p : EconomicsParams) : ℝ :=
    E.ExpectedUtility s a - (p.lambda_R * E.ExpectedRisk s a) - (p.lambda_C * E.TotalCostOwnership a)

  theorem mass_energy_value_equiv 
      {S A : Type*} [M : EfficientMarket S A]
      (s : S) (a : A) (p : EconomicsParams)
      (h_eq : M.IsEquilibrium s a p)
      : ValueObjective s a p ≤ p.lambda_v * M.TotalCostOwnership a := by
    unfold ValueObjective
    have h := M.no_arbitrage s a p h_eq
    have h_expand : (p.lambda_v + p.lambda_C) * M.TotalCostOwnership a = 
        p.lambda_v * M.TotalCostOwnership a + p.lambda_C * M.TotalCostOwnership a := 
        add_mul p.lambda_v p.lambda_C (M.TotalCostOwnership a)
    linarith

end CoAI.Economics
