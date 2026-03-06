import CoAI.Economics
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

namespace CoAI.Economics.Example

  open CoAI.Economics

  inductive UnitState | s deriving DecidableEq
  inductive UnitAction | a deriving DecidableEq

  instance : EfficientMarket UnitState UnitAction where
    ExpectedUtility := fun _ _ => 1
    ExpectedRisk := fun _ _ => 0
    TotalCostOwnership := fun _ => 1
    IsEquilibrium := fun _ _ params => params.lambda_R ≥ 0 ∧ params.lambda_v + params.lambda_C ≥ 1
    no_arbitrage := by
      intro st_act act_act p_act ⟨_, _⟩
      simp
      linarith

  example : ∃ (st_val : UnitState) (act_val : UnitAction) (prm_val : EconomicsParams), EfficientMarket.IsEquilibrium st_val act_val prm_val := 
    ⟨.s, .a, ⟨0, 0, 1⟩, by constructor <;> norm_num⟩

end CoAI.Economics.Example
