-- =========================================================================
-- THE CALCULUS OF AI: FORMAL VERIFICATION SUBSTRATE (v3.1.1)
-- =========================================================================
import Mathlib.Data.Real.Basic
import Mathlib.Data.Countable.Defs
import Mathlib.Probability.ProbabilityMassFunction.Basic
import Mathlib.Probability.ProbabilityMassFunction.Monad
import Mathlib.Tactic.Linarith

noncomputable section

namespace CoAI.Substrate

  class CoalgebraicSystem (Program State TraceSpace : Type*) where
    denotational : Program → State → TraceSpace
    realization  : Program → State → PMF State
    observation  : PMF State → TraceSpace
    traceMeasure : (State → TraceSpace) → State → TraceSpace
    traceMeasure_def : ∀ f s, traceMeasure f s = f s

  class Coherent (Program State TraceSpace : Type*) 
      extends CoalgebraicSystem Program State TraceSpace where
    coherence : ∀ (p : Program) (s : State),
      observation (realization p s) = traceMeasure (denotational p) s

  -- Satisfiability Witness
  inductive Bit | zero | one deriving DecidableEq

  instance : Countable Bit :=
    Function.Injective.countable 
      (f := fun | .zero => (0 : ℕ) | .one => 1)
      (fun a b h => by cases a <;> cases b <;> simp_all)

  instance : Coherent Bit Bit (PMF Bit) where
    denotational _ s    := PMF.pure s
    realization  _ s    := PMF.pure s
    observation  pmf    := pmf
    traceMeasure f s    := f s
    traceMeasure_def _ _ := rfl
    coherence    _ _    := rfl

end CoAI.Substrate
