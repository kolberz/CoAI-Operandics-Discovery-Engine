# The Complete Unified Framework

## Everything Is a Representation Change

---

## Prologue: The One Idea

In 1999, a programmer at id Software wrote a function to compute `1/√x`. Instead of using the mathematical definition, they reinterpreted the 32-bit float as an integer, performed one subtraction with a magic constant, and reinterpreted the result back as a float. It was 4× faster and accurate to within a fraction of a percent.

The function works because IEEE 754 floats are not what they appear to be. A float's bit pattern — when read as an integer — is approximately proportional to the **logarithm** of the number it represents. So `1/√x = x^(-0.5)`, and in log space, multiplying by −0.5 is just an integer shift and subtract. The entire discipline of "Quake-style" optimization descends from this single observation.

But the observation is not about floats. It is about **representation**. The float format secretly encodes a logarithm, and logarithms turn multiplication into addition, division into subtraction, and powers into scaling. The "hack" is just arithmetic in the correct domain.

This document catalogs 32 techniques built on this principle and 8 more from adjacent domains, organizes them by the deeper structural recognitions that make them work, shows how they combine into complete systems, and ultimately traces everything back to three fundamental moves that recur across all of mathematics, computer science, and physics:

1. **Change of Basis** — diagonalize the operator
2. **Change of Domain** — map to where operations are cheaper
3. **Change of Granularity** — decompose into levels

Every technique, every combination, and every structural recognition in this document is one or more of these three moves.

---

## Part I — The Three Fundamental Moves

### Move 1: Change of Basis

Given an operator A that is expensive in the standard basis, find a matrix P such that P⁻¹AP is diagonal (or triangular, or block-diagonal). In the new basis, applying A costs O(N) instead of O(N²).

**Examples across all domains:**

| Problem | Expensive form | Diagonalizing basis | Cheap form |
|---|---|---|---|
| Convolution | O(N²) sum of products | Fourier basis | O(N) pointwise multiply |
| Linear recurrence h_t = Ah_{t-1} | O(T) sequential steps | Eigenvectors of A | O(log T) parallel scan |
| PDE solution | Coupled differential equations | Spectral basis | Decoupled scalar ODEs |
| Spectral rendering | 81-wavelength loop | PCA eigenbasis of reflectance | 3-coefficient multiply |
| Covariance estimation | N×N matrix operations | PCA/SVD eigenvectors | Diagonal eigenvalue ops |
| Circuit analysis | System of coupled ODEs | Laplace/Fourier transform | Algebraic impedance |
| Graph algorithms | Adjacency matrix ops | Graph Fourier basis | Spectral clustering |

**The test:** When you encounter an O(N²) or O(N³) operation, ask: "Does this operator commute with something? Does it have eigenvectors? Can I diagonalize it?"

---

### Move 2: Change of Domain

Given a problem in domain A where operations are expensive, find an isomorphism φ: A → B where the corresponding operations are cheap.

| Domain A (expensive) | Domain B (cheap) | The map φ | What becomes cheaper |
|---|---|---|---|
| Positive reals (multiply) | Logarithms (add) | log(x) | Multiply → add, power → scale |
| Geometry (boolean ops) | SDFs (min/max) | SDF(shape) | Union → min, intersection → max |
| Probability (Bayes) | Vectors on simplex | Distribution → vector | Update → pointwise multiply |
| Programs (execution) | Proofs (verification) | Curry-Howard | Correctness → type checking |
| Polynomials over GF(2) | Bit strings (XOR/AND) | Coefficient → bit | Polynomial add → XOR |
| Floats (comparison) | Order-preserving ints | Float-flip transform | Float sort → integer radix |
| Continuous spectra | PCA coefficients | Projection onto eigenbasis | Per-wavelength → coefficient ops |

---

### Move 3: Change of Granularity

Given a problem with structure at multiple scales, decompose it into a hierarchy where each level is simple and levels communicate through a narrow interface.

| Problem | Flat representation | Hierarchical decomposition | What becomes cheaper |
|---|---|---|---|
| Address translation | 48-bit integer | 4-level page table | Sparse mapping |
| Number representation | Fixed-point integer | Float (sign+exp+mantissa) | Dynamic range |
| Morton/Z-order key | Concatenated coords | Interleaved bits (octree) | Spatial locality |
| Long context attention | O(N²) full attention | 3-level: exact+sparse+summary | Bounded memory |
| Numerical precision | One format everywhere | Adaptive per-tensor | Memory ∝ precision need |
| Spatial indexing | Brute-force scan | BVH/octree/grid hierarchy | O(log N) queries |

---

## Part II — The Four Primitive Operations

### Primitive 1: The Hash (SplitMix64)

```cpp
__host__ __device__ __forceinline__
uint64_t SplitMix64(uint64_t x) {
    x += 0x9E3779B97F4A7C15ull;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
    return x ^ (x >> 31);
}
```

Serves 7 techniques: Phantom Mask (#1), Holographic Embed (#8), Sign-Router (#18), Polarity-Dropout (#17), Chaos-Sample (#21), Stochastic-Alpha (N8), Galois-Noise (N3).

### Primitive 2: The Float Bridge (Float-Flip Transform)

```cpp
__host__ __device__ __forceinline__
uint32_t FloatToSortable(float f) {
    uint32_t bits; memcpy(&bits, &f, sizeof(bits));
    uint32_t mask = -(bits >> 31);
    return bits ^ (mask | 0x80000000u);
}
```

Serves 6 techniques: Radix-Select (#10), Confidence-Gate (#12), Exponent-Clip (#16), Shift-Max (#4), Reciprocal Gate (#7), Decay-Shift (#22).

### Primitive 3: The Log-Add LUT (Table-Add Core)

```cpp
constexpr int FRAC_BITS = 8;
constexpr int LUT_SIZE  = 4096;
static int16_t g_LogAddLUT[LUT_SIZE + 1];

void InitLogAddLUT() {
    for (int d = 0; d <= LUT_SIZE; d++) {
        double x = -(double)d / (double)(1 << FRAC_BITS);
        g_LogAddLUT[d] = (int16_t)lround(log(1.0 + exp(x)) * (double)(1 << FRAC_BITS));
    }
}

__host__ __device__ __forceinline__
int32_t LogAdd(int32_t a, int32_t b) {
    int32_t mx = (a > b) ? a : b;
    int32_t diff = (a > b) ? (a - b) : (b - a);
    if (diff > LUT_SIZE) return mx;
    return mx + (int32_t)g_LogAddLUT[diff];
}
```

Serves 5 techniques: Table-Add Core (#9), Log-Add Core (#5), Recursive Shift-Max (R7), Bit-Mask Norm (#6 LNS), Sigmoid-Shift (#14 LNS).

### Primitive 4: The Binary Sketch (SimHash)

```cpp
void SimHashSketch(const float* vec, int dim, const float* hyperplanes,
                   uint64_t* sketch, int num_bits) {
    for (int b = 0; b < num_bits; b++) {
        float dot = 0.0f;
        for (int d = 0; d < dim; d++)
            dot += vec[d] * hyperplanes[b * dim + d];
        if (dot >= 0.0f) sketch[b/64] |= (1ull << (b%64));
    }
}

__host__ __device__ __forceinline__
int SketchDistance(const uint64_t* a, const uint64_t* b, int num_words) {
    int dist = 0;
    for (int w = 0; w < num_words; w++)
        dist += __popcountll(a[w] ^ b[w]);
    return dist;
}
```

Serves 5 techniques: Polarity Gate (#2), Hamming-Gate (#15), Sign-Router (#18), Census-Lock (N6), Morton-Z (#11).

### How the Four Primitives Interconnect

```
   ┌─────────┐    ┌──────────────┐
   │  HASH   │───▶│ BINARY SKETCH │
   │(SplitMix)│   │  (SimHash)    │
   └────┬────┘    └──────┬───────┘
        │   ┌────────────┘
        ▼   ▼
   ┌─────────────┐    ┌──────────────┐
   │FLOAT BRIDGE │───▶│ LOG-ADD LUT  │
   │(Float-Flip) │    │ (Table-Add)  │
   └─────────────┘    └──────────────┘
```

~200 lines of code total → foundation for 23 of 32 techniques + all 7 recursive + 6 of 8 novel.

---

## Part III — The Complete Technique Catalog

### Category 1: Replace Expensive Math with Cheap Math (Move 2)

#### #4 · Shift-Max (Fast Softmax Exp)

Approx (<0.3% error). `exp(x)` via IEEE exponent field write + polynomial correction.

#### #7 · Reciprocal Gate (Fast 1/x)

Approx (<0.1% after 1 NR, <1 ULP after 2). Magic constant + Newton-Raphson + special values.

#### #5 · Log-Add Core (True LNS Arithmetic)

Approx. Store as fixed-point log₂. Multiply = int add. Accumulate = LUT. Fix: IEEE bits ≠ logarithms.

#### #9 · Table-Add Core (LNS Inference Engine)

Approx. Full inference in LNS. 5-10× energy reduction per MAC on custom silicon.

#### #13 · Binary-RoPE (CORDIC Rotation)

Approx. Sin/cos via shift-and-add. Wins on FPGA/MCU only (GPU trig already fast).

#### #14 · Sigmoid-Shift (Fast Activation)

Approx (<0.2%). Padé polynomial + FastRcp for denominator.

#### N5 · Fresnel-Bit (Fast Power-of-N)

Approx (~12% raw). For integer powers, plain multiplies are faster AND exact.

### Category 2: Reduce Search/Sort via Integer Domain (Move 2 + Move 1)

#### #10 · Radix-Select (O(N) Top-k on Floats)

**Exact.** Float-flip + MSB-first bit partitioning. O(n) average.

#### #12 · Confidence-Gate (Provable Softmax Skip)

**Exact.** Gap >= T·ln((V-1)·c/(1-c)) proves P(top1) >= c. Skips softmax ~40%.

#### #11 · Morton-Z (Locality-Preserving Spatial Key)

**Exact** as key; prefilter-only for NN search. Useful for d ≤ ~10.

### Category 3: Reduce Dimensionality via Sketching (Move 2)

#### #2/#15 · Polarity Gate + Hamming-Gate (Sub-Quadratic Attention)

Algo-change. SimHash + LSH bucketing. Must have bucketing for sub-quadratic.

#### N6 · Census-Lock (Stereo Matching)

Algo-change. Prior art: Zabih & Woodfill 1994.

### Category 4: Modify Training/Inference Algorithm

#### #1 · Phantom Mask — deterministic dropout via SplitMix64

#### #17 · Polarity-Dropout — sign-flip regularization (post-nonlinearity only)

#### #8 · Holographic Embed — hash embeddings (multi-hash + sign + residual)

#### #6 · Bit-Mask Norm — L1-based normalization (calibrated correction)

#### #18 · Sign-Router — hash-based MoE routing

#### #16 · Exponent-Clip — hybrid gradient clipping (exponent fast-path)

#### #19 · Infinity-Mask — branchless causal mask (**only correct technique as originally stated**)

#### #20 · Exponent-Quant — KV cache compression (block-scaled FP8)

#### #21 · Chaos-Sample — whitened hardware entropy

#### #22 · Decay-Shift — weight decay in fixed-point only (broken for IEEE)

#### #23 · Ghost-Momentum — **BROKEN.** LSBs destroyed. Use 8-bit Adam

#### #24 · Fractal-Stack — multi-timescale additive decay summaries

#### #3 · Mantissa-Step — **UNFIXABLE.** Use Adam

### Category 5: Novel Domain-Specific

#### N1 · Symplectic-Shift — integer lattice physics (exact shadow Hamiltonian)

#### N2 · Bit-Wave — Manhattan BFS via bit-packed wavefront

#### N3 · Galois-Noise — CLMUL procedural noise + SplitMix64 finalizer

#### N4 · Eigen-Spectrum — PCA spectral rendering (product tensor T_ijk)

#### N7 · Bloom-Phase — bitmask collision prefilter (exact rejection)

#### N8 · Stochastic-Alpha — order-independent transparency + TAA

### Correctness Summary

| Status | Techniques |
|---|---|
| **Exact** | #10 Radix-Select, #12 Confidence-Gate, #19 Infinity-Mask, #16 Exponent-Clip |
| **Approx** | #4, #5, #6, #7, #9, #13, #14, #20, N4, N5 |
| **Algo-change** | #1, #2, #8, #15, #17, #18, #21, #24, N1, N2, N3, N6, N7, N8 |
| **Broken** | #3 Mantissa-Step, #23 Ghost-Momentum |
| **Fixed-point only** | #22 Decay-Shift |
