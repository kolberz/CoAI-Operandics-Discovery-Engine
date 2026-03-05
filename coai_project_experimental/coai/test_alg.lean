import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Ring

open Real

theorem test_alg (ε A M : ℝ) :
        (-(ε ^ 2)) / (2 * (A / M)) = - (M * (ε ^ 2)) / (2 * A) := by
      calc
        (-(ε ^ 2)) / (2 * (A / M))
            = (-(ε ^ 2)) / ((2 * A) / M) := by rw [mul_div_assoc]
        _   = (-(ε ^ 2)) * M / (2 * A) := by rw [div_div]
        _   = - (M * (ε ^ 2)) / (2 * A) := by
                congr 1
                ring
