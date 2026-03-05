import Mathlib.Data.Matrix.Basic

open scoped BigOperators
open Matrix

namespace KernelAttention

variable {𝕜 : Type*} [Field 𝕜]
variable {N D R Dv : Type*}
variable [Fintype N] [Fintype D] [Fintype R] [Fintype Dv]
variable [DecidableEq N] [DecidableEq D] [DecidableEq R] [DecidableEq Dv]

-- Feature maps are opaque: only their output shapes matter.
variable (ΦQ : Matrix N D 𝕜 → Matrix N R 𝕜)
variable (ΦK : Matrix N D 𝕜 → Matrix N R 𝕜)

-- “Quadratic” kernel attention (materializes N×N internally)
def AttnKernelQuad (Q : Matrix N D 𝕜) (K : Matrix N D 𝕜) (V : Matrix N Dv 𝕜) :
    Matrix N Dv 𝕜 :=
  ((ΦQ Q) * (Matrix.transpose (ΦK K))) * V

-- “Linearized” kernel attention (never materializes N×N)
def AttnKernelLin (Q : Matrix N D 𝕜) (K : Matrix N D 𝕜) (V : Matrix N Dv 𝕜) :
    Matrix N Dv 𝕜 :=
  (ΦQ Q) * ((Matrix.transpose (ΦK K)) * V)

-- Formal certification of the O(N) linear bypass mapping synthesized by MCTS
theorem attnKernel_factorize (Q : Matrix N D 𝕜) (K : Matrix N D 𝕜) (V : Matrix N Dv 𝕜) :
    AttnKernelQuad (ΦQ := ΦQ) (ΦK := ΦK) Q K V
      = AttnKernelLin (ΦQ := ΦQ) (ΦK := ΦK) Q K V := by
  -- unfolds to `((A ⬝ B) ⬝ C) = (A ⬝ (B ⬝ C))` guaranteeing absolute algebraic equivalence
  simp [AttnKernelQuad, AttnKernelLin, Matrix.mul_assoc]

-- ==========================================
-- Phase 14: Normalized Linear Attention Certification
-- ==========================================

-- 1. Bridging the "macro" OuterN operator to concrete matrix algebra
-- OuterN is semantically a sum of outer products over N
def OuterN (K_feats : Matrix N R 𝕜) (V : Matrix N Dv 𝕜) : Matrix R Dv 𝕜 :=
  fun i j => ∑ n : N, K_feats n i * V n j

-- Theorem: OuterN is mathematically identical to transpose(ΦK) ⬝ V
theorem outerN_eq_transpose_mul (K_feats : Matrix N R 𝕜) (V : Matrix N Dv 𝕜) :
    OuterN K_feats V = (Matrix.transpose K_feats) * V := by
  ext i j
  simp [OuterN, Matrix.mul_apply, Matrix.transpose_apply]

-- 2. Normalization
-- Define the "ones" vector
def ones : Matrix N (Fin 1) 𝕜 := fun _ _ => 1

-- Implement `Normalize` total function semantics utilizing scalar masking via `inv 0 = 0` convention 
-- which avoids the need to thread `hden : denom ≠ 0` everywhere.
def Normalize (Num : Matrix N Dv 𝕜) (Denom : Matrix N (Fin 1) 𝕜) : Matrix N Dv 𝕜 :=
  fun n d => Num n d / Denom n 0

-- 3. The full Normalized MCTS rewrite theorem:
theorem attnKernel_normalized_factorize
  (Q : Matrix N D 𝕜) (K : Matrix N D 𝕜) (V : Matrix N Dv 𝕜) :
  Normalize ( (ΦQ Q) * ((Matrix.transpose (ΦK K)) * V) )
            ( (ΦQ Q) * ((Matrix.transpose (ΦK K)) * ones) )
  =
  Normalize ( ((ΦQ Q) * (Matrix.transpose (ΦK K))) * V )
            ( ((ΦQ Q) * (Matrix.transpose (ΦK K))) * ones ) := by
  -- Apply `mul_assoc` to both the Numerator and the Denominator
  rw [Matrix.mul_assoc (ΦQ Q) (Matrix.transpose (ΦK K)) V]
  rw [Matrix.mul_assoc (ΦQ Q) (Matrix.transpose (ΦK K)) ones]

end KernelAttention
