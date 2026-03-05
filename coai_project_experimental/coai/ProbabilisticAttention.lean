/-
  ProbabilisticAttention.lean — Level 1: Expected Linear = Exact Softmax

  Proves that if the kernel is unbiased, the Expected Value of the
  linearized O(N) route equals the exact O(N²) Softmax route.
-/

import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.Tactic.Positivity
import Mathlib.Data.Matrix.Basic

open MeasureTheory ProbabilityTheory
open scoped BigOperators
open Matrix

namespace StochasticAttention

variable {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
variable {N D R Dv : Type*} [Fintype N] [Fintype D] [Fintype R] [Fintype Dv]
variable [DecidableEq N] [DecidableEq D] [DecidableEq R] [DecidableEq Dv]

-- 1. Import our definitions from Phase 13
def AttnKernelQuad (ΦQ : Matrix N D ℝ → Matrix N R ℝ) (ΦK : Matrix N D ℝ → Matrix N R ℝ)
    (Q : Matrix N D ℝ) (K : Matrix N D ℝ) (V : Matrix N Dv ℝ) : Matrix N Dv ℝ :=
  ((ΦQ Q) * (ΦK K)ᵀ) * V

def AttnKernelLin (ΦQ : Matrix N D ℝ → Matrix N R ℝ) (ΦK : Matrix N D ℝ → Matrix N R ℝ)
    (Q : Matrix N D ℝ) (K : Matrix N D ℝ) (V : Matrix N Dv ℝ) : Matrix N Dv ℝ :=
  (ΦQ Q) * ((ΦK K)ᵀ * V)

-- The deterministic equivalence certified by the E-Graph / MCTS
theorem attnKernel_factorize (ΦQ ΦK : Matrix N D ℝ → Matrix N R ℝ)
    (Q K : Matrix N D ℝ) (V : Matrix N Dv ℝ) :
    AttnKernelQuad ΦQ ΦK Q K V = AttnKernelLin ΦQ ΦK Q K V := by
  simp [AttnKernelQuad, AttnKernelLin, Matrix.mul_assoc]

-- 2. Define the True Softmax Kernel and the Random Feature Map Φ
variable (SoftmaxKernel : Matrix N N ℝ)
variable (Φ : Ω → Matrix N D ℝ → Matrix N R ℝ)

/-- The Unbiased Estimator Hypothesis:
    The expected value of the inner product of our random features
    exactly equals the true softmax kernel. -/
def IsUnbiasedKernel (Q K : Matrix N D ℝ) : Prop :=
  ∀ i j, ∫ ω, ∑ r : R, (Φ ω Q) i r * (Φ ω K) j r ∂volume = SoftmaxKernel i j

-- Integrability hypothesis: Required by Lean 4 to prove the Lebesgue integral can be split
variable (Q K : Matrix N D ℝ) (V : Matrix N Dv ℝ)
variable (h_int : ∀ i j, Integrable (fun ω => ∑ r : R, (Φ ω Q) i r * (Φ ω K) j r) volume)

/-- LEVEL 1 TARGET:
    If the kernel is unbiased, the Expected Value of the linearized O(N) route
    equals the exact O(N²) Softmax route. -/
theorem expected_linear_eq_exact_softmax
    (h_int : ∀ i j, Integrable (fun ω => ∑ r : R, (Φ ω Q) i r * (Φ ω K) j r) volume)
    (h_unbiased : IsUnbiasedKernel SoftmaxKernel Φ Q K) :
    ∀ i j, ∫ ω, (AttnKernelLin (Φ ω) (Φ ω) Q K V) i j ∂volume =
           (SoftmaxKernel * V) i j := by
  intro i j

  -- Step A: Substitute the O(N) form for the O(N²) form using our Phase 13 theorem
  have h_det : (fun ω => (AttnKernelLin (Φ ω) (Φ ω) Q K V) i j) =
               (fun ω => (AttnKernelQuad (Φ ω) (Φ ω) Q K V) i j) := by
    ext ω
    rw [← attnKernel_factorize]
  rw [h_det]

  -- Step B: Expand the definition of Matrix multiplication to expose the summations
  have h_expand : (fun ω => (AttnKernelQuad (Φ ω) (Φ ω) Q K V) i j) =
      fun ω => ∑ k : N, (∑ r : R, (Φ ω Q) i r * (Φ ω K) k r) * V k j := by
    ext ω
    simp [AttnKernelQuad, Matrix.mul_apply, Matrix.transpose_apply]
  rw [h_expand]

  -- Step C: Apply Linearity of Expectation (Integral of sum = sum of integrals)
  rw [integral_finset_sum]

  -- Step D: Pull the constant matrix V out of the random variable expectation
  have h_pull : (∑ k : N, ∫ ω, (∑ r : R, (Φ ω Q) i r * (Φ ω K) k r) * V k j ∂volume) =
                ∑ k : N, (∫ ω, ∑ r : R, (Φ ω Q) i r * (Φ ω K) k r ∂volume) * V k j := by
    congr 1
    ext k
    exact integral_mul_const (V k j) _
  rw [h_pull]

  -- Step E: Apply the Unbiased Kernel Hypothesis to collapse the random features
  have h_sub : (∑ k : N, (∫ ω, ∑ r : R, (Φ ω Q) i r * (Φ ω K) k r ∂volume) * V k j) =
               ∑ k : N, SoftmaxKernel i k * V k j := by
    congr 1
    ext k
    rw [h_unbiased i k]
  rw [h_sub]

  -- Step F: Refold the summation back into the formal Matrix.mul definition
  rfl

  -- Sub-proof: Prove to the compiler that the split sum remains integrable
  intro k _
  exact (h_int i k).mul_const (V k j)

end StochasticAttention
