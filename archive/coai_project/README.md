# Operandics — CoAI Certified Attention Stack

> **CoAI (The Calculus of AI)** provides machine-checked proofs that **linear attention is a mathematically exact, probabilistically bounded substitute for softmax attention**, verified end-to-end in Lean 4 against Mathlib.

[![Lean 4](https://img.shields.io/badge/Lean-v4.29.0--rc1-blue)]()
[![Mathlib](https://img.shields.io/badge/Mathlib-latest-green)]()
[![Build](https://img.shields.io/badge/Build-2880%20jobs%20✓-brightgreen)]()

---

## Overview

The CoAI stack is a **5-layer certified stack** that formally proves the mathematical pipeline from quadratic softmax attention (O(N²)) down to its linear-time random-feature approximation (O(N)), and bounds the approximation error with sub-Gaussian concentration inequalities — all machine-checked in Lean 4 with Mathlib.

The capstone theorem `certified_attention_contract` simultaneously certifies:

1. **Unbiasedness**: The FAVOR+ estimator's expectation equals the exact softmax kernel.
2. **Concentration**: For any user-chosen (ε, δ), the approximation error exceeds ε with probability at most δ, given sufficiently many random features m.

### Axiom Audit

```
'CoAI.SBOM.certified_attention_contract' depends on axioms: [propext, Classical.choice, Quot.sound]
```

**Zero domain-specific axioms remain.** Both the Gaussian characteristic function identity and the Hoeffding sub-Gaussian tail bound have been rigorously proven and extracted building off Mathlib's `gaussianReal` and `HasSubgaussianMGF` distributions. Everything is proved from first principles.

---

## Architecture: The 5-Layer Stack

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 5: CertifiedStack.lean — SBOM / Capstone Contract    │
│           certified_attention_contract : Unbiased ∧ Bounded │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Control.lean — Runtime Safety Envelope            │
│           Ville's Maximal Inequality (Optional Stopping)    │
│           PMF-Markov Bridge · Algebraic Drift Bounds        │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Concentration.lean — Statistical Guarantees       │
│           favor_bound_delta: P(|error| ≥ ε) ≤ δ            │
│           Sub-Gaussian / Hoeffding tail bound               │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: FAVOR.lean — Kernel Unbiasedness                  │
│           favor_is_unbiased (m=1): E[φ(q)·φ(k)] = exp⟨q,k⟩│
│           favor_is_unbiased_m: Averaged estimator lifts     │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: ProbabilisticAttention.lean — Structural Bridge   │
│           expected_linear_eq_exact_softmax                  │
│           E[O(N) route] = O(N²) softmax route               │
├─────────────────────────────────────────────────────────────┤
│  Layer 0: LinearRouting.lean — Algebraic Factorization      │
│           attnKernel_factorize: (ΦQ·ΦKᵀ)·V = ΦQ·(ΦKᵀ·V)  │
│           Matrix.mul_assoc (the O(N²) → O(N) rewrite)       │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Reference

| Module | Lines | Purpose |
|--------|------:|---------|
| `Substrate.lean` | 43 | Coalgebraic system foundations: `CoalgebraicSystem`, `Coherent` typeclasses, satisfiability witness |
| `LinearRouting.lean` | 71 | Deterministic O(N²)→O(N) matrix factorization via `mul_assoc`; normalized attention variant |
| `ExpectedRouting.lean` | 76 | Expectation-level bridge: if kernel unbiased, E[normalized linear attn] = softmax attn |
| `ProbabilisticAttention.lean` | 102 | Level 1 — Bochner integral proof: E[linear route] = exact softmax route per matrix entry |
| `FAVOR.lean` | 156 | Level 2 — FAVOR+ random Fourier features: `cos/sin` feature map unbiasedness (m=1 and m-averaged) |
| `GaussianCharFun.lean` | 85 | Bridge: Proves E[cos(tx)] = exp(-t²/2) via Mathlib's `charFun_gaussianReal` |
| `FavorSubGaussian.lean` | 111 | Bridge: Proves generic sub-Gaussian tail bounds via Mathlib's `HasSubgaussianMGF` |
| `Concentration.lean` | 84 | Level 3 — Sub-Gaussian tail: P(\|error\| ≥ ε) ≤ δ given m ≥ f(ε, δ, ‖q‖, ‖k‖) |
| `Composition.lean` | 76 | Sequential module composition: ε₁ + ε₂ union bound over PMF bind chains |
| `Control.lean` | 244 | Runtime safety: PMF-Markov bridge, algebraic drift, Ville's maximal inequality via optional stopping |
| `Economics.lean` | 40 | Value-risk equilibrium: `mass_energy_value_equiv` under no-arbitrage constraints |
| `CertifiedStack.lean` | 47 | Capstone SBOM: `certified_attention_contract` joining unbiasedness ∧ concentration |

---

## Key Theorems

### `attnKernel_factorize` — Layer 0

```
(ΦQ(Q) · ΦK(K)ᵀ) · V = ΦQ(Q) · (ΦK(K)ᵀ · V)
```

The algebraic identity that rewrites O(N²) dot-product attention into O(N) linear attention. Proved by `Matrix.mul_assoc`.

### `favor_is_unbiased` — Layer 2

```
E_ω[Σᵢ φᵢ(ω,q) · φᵢ(ω,k)] = exp(⟨q,k⟩)
```

The FAVOR+ random Fourier feature map is an unbiased estimator of the Gaussian softmax kernel. Proved via the cos-addition formula and the Gaussian characteristic function axiom.

### `favor_is_unbiased_m` — Layer 2 (Generalization)

```
E_ω[(1/m) Σᵣ Σᵢ φᵢ(ωᵣ,q) · φᵢ(ωᵣ,k)] = exp(⟨q,k⟩)
```

The averaged estimator over m i.i.d. draws inherits unbiasedness by linearity of expectation.

### `favor_bound_delta` — Layer 3

```
P(|KernelError_m(q,k)| ≥ ε) ≤ δ
    provided  m ≥ (2·exp(2‖q‖·‖k‖)·log(2/δ)) / ε²
```

Converts the Hoeffding tail axiom into an actionable deployment knob: choose (ε, δ) and compute the minimum m.

### `ville_finite_horizon` — Layer 4

```
ofReal(c) · μ(A) ≤ ofReal(E[M₀])
    where A = {ω | ∃ k ∈ [0,N], c ≤ M_k(ω)}
```

Ville's maximal inequality for nonneg supermartingales via Mathlib's optional stopping theorem. Provides uniform-in-time safety guarantees for the L0 hypervisor.

### `certified_attention_contract` — Layer 5

```
  (E[FAVOR+(q,k,m)] = Softmax(q,k))
∧ (P(|error| ≥ ε) ≤ δ)
```

The capstone: unbiasedness and concentration in a single conjunctive certificate.

---

## Building

### Prerequisites

- [elan](https://github.com/leanprover/elan) (Lean version manager)
- ~8 GB RAM (Mathlib compilation)

### Build Commands

```bash
# Full certified stack (≈ 2880 jobs)
lake build CoAI.CertifiedStack

# Individual modules
lake build CoAI.FAVOR
lake build CoAI.Control
```

### Toolchain

```
leanprover/lean4:v4.29.0-rc1
```

---

## Project Structure

```
coai_project/
├── lakefile.lean              # Lake build configuration
├── lean-toolchain             # Lean 4 v4.29.0-rc1
├── lake-manifest.json         # Pinned Mathlib dependency
├── CoAI/
│   ├── Substrate.lean         # Coalgebraic foundations
│   ├── LinearRouting.lean     # O(N²) → O(N) factorization
│   ├── ExpectedRouting.lean   # E[linear] = softmax bridge
│   ├── ProbabilisticAttention.lean  # Level 1: Bochner integral proof
│   ├── GaussianCharFun.lean   # Mathlib Bridge: Gaussian charFun
│   ├── FavorSubGaussian.lean  # Mathlib Bridge: Sub-Gaussian tails
│   ├── FAVOR.lean             # Level 2: FAVOR+ unbiasedness
│   ├── Concentration.lean     # Level 3: Sub-Gaussian concentration
│   ├── Composition.lean       # Sequential risk composition
│   ├── Control.lean           # Ville's inequality / optional stopping
│   ├── Economics.lean         # Value-risk equilibrium
│   └── CertifiedStack.lean    # Capstone SBOM
└── coai/                      # Python runtime interface
    ├── interface.py           # L0 hypervisor telemetry bridge
    └── runtime.py             # Python ↔ Lean runtime
```

---

## Citation

If you use this work, please cite:

```bibtex
@software{coai2026,
  title   = {Operandics: The CoAI Certified Attention Stack},
  year    = {2026},
  note    = {Lean 4 / Mathlib. 5-layer proof: algebraic factorization,
             FAVOR+ unbiasedness, sub-Gaussian concentration,
             Ville's maximal inequality, capstone SBOM.},
  url     = {https://github.com/coai-project/coai}
}
```

---

## License

This project is provided as-is for research and educational purposes.
