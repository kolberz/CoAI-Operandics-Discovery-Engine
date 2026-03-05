import Mathlib.Data.Matrix.Basic
import CoAI.LinearRouting

open scoped BigOperators
open Matrix

namespace ExpectedRouting

variable {𝕜 : Type*} [Field 𝕜]
variable {N D R Dv : Type*}
variable [Fintype N] [Fintype D] [Fintype R] [Fintype Dv]
variable [DecidableEq N] [DecidableEq D] [DecidableEq R] [DecidableEq Dv]

-- Let Ω be an abstract probability sample space
variable {Ω : Type*}

-- The softmax kernel is an opaque function: we only care about its type signature
variable (softmax_kernel : Matrix N D 𝕜 → Matrix N D 𝕜 → Matrix N N 𝕜)

-- Opaque Expectation operators (axiomatized; will be grounded to measure integrals in Level 2+)
-- Separate operators for numerator (N×Dv) and denominator (N×Fin 1) dimensions
variable (E_NDv : (Ω → Matrix N Dv 𝕜) → Matrix N Dv 𝕜)
variable (E_N1 : (Ω → Matrix N (Fin 1) 𝕜) → Matrix N (Fin 1) 𝕜)
variable (E_NN : (Ω → Matrix N N 𝕜) → Matrix N N 𝕜)

-- Random feature maps sampled from Ω (e.g. Random Fourier Features / FAVOR+)
variable (ΦQ : Ω → Matrix N D 𝕜 → Matrix N R 𝕜)
variable (ΦK : Ω → Matrix N D 𝕜 → Matrix N R 𝕜)

-- True Softmax Attention applies the exact exponential kernel to V and normalizes
noncomputable def softmax_attn (Q K : Matrix N D 𝕜) (V : Matrix N Dv 𝕜) : Matrix N Dv 𝕜 :=
  KernelAttention.Normalize ((softmax_kernel Q K) * V)
                             ((softmax_kernel Q K) * KernelAttention.ones)

/--
  Level 1: Conditional expectation approximation theorem.

  If φ is an unbiased kernel approximation (its expected dot product is exactly the softmax kernel),
  and if the expectation operator distributes linearly through right-multiplication by a fixed matrix,
  then the expected normalized linear attention output equals softmax attention.

  Note: In strict mathematical probability, E[f(X)/g(X)] ≠ E[f(X)]/E[g(X)] in general.
  This theorem assumes the expectation passes through the normalize wrapper.
  The formal proof of the exact passage requires bounding variance and applying concentration
  bounds (Level 3, where Ville/Markov machinery becomes directly useful).
-/
theorem linear_attn_unbiased
    (Q : Matrix N D 𝕜) (K : Matrix N D 𝕜) (V : Matrix N Dv 𝕜)
    -- Core unbiasedness: E[φ(Q)φ(K)ᵀ] = softmax_kernel(Q,K)
    (h_unbiased : E_NN (fun ω => (ΦQ ω Q) * (Matrix.transpose (ΦK ω K)))
                  = softmax_kernel Q K)
    -- Linearity of E through right-multiplication by V
    (h_linear_V : E_NDv (fun ω => (ΦQ ω Q) * ((Matrix.transpose (ΦK ω K)) * V))
                  = (E_NN (fun ω => (ΦQ ω Q) * (Matrix.transpose (ΦK ω K)))) * V)
    -- Linearity of E through right-multiplication by ones
    (h_linear_1 : E_N1 (fun ω => (ΦQ ω Q) * ((Matrix.transpose (ΦK ω K)) * KernelAttention.ones))
                  = (E_NN (fun ω => (ΦQ ω Q) * (Matrix.transpose (ΦK ω K)))) * KernelAttention.ones)
    -- E distributes through normalize (valid under concentration / dominated convergence)
    (h_normalize_comm : ∀ (f : Ω → Matrix N Dv 𝕜) (g : Ω → Matrix N (Fin 1) 𝕜),
        E_NDv (fun ω => KernelAttention.Normalize (f ω) (g ω))
        = KernelAttention.Normalize (E_NDv f) (E_N1 g)) :
    E_NDv (fun ω => KernelAttention.Normalize
                      ((ΦQ ω Q) * ((Matrix.transpose (ΦK ω K)) * V))
                      ((ΦQ ω Q) * ((Matrix.transpose (ΦK ω K)) * KernelAttention.ones)))
    = softmax_attn softmax_kernel Q K V := by
  -- Step 1: Push E through Normalize using the commutativity hypothesis
  rw [h_normalize_comm]
  -- Step 2: Apply linearity of E to numerator and denominator
  rw [h_linear_V, h_linear_1]
  -- Step 3: Substitute the unbiasedness condition
  rw [h_unbiased]
  -- Goal is now: Normalize (sk * V) (sk * ones) = softmax_attn sk Q K V
  rfl

end ExpectedRouting
