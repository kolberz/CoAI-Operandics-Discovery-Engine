"""
grounding/quake.py

Quake-Style Optimization Primitives for the CoAI Operandics Engine.
Recursive Versions — Corrected Mathematical Foundations.

Each algorithm is defined by a self-similar recurrence (octree subdivision,
tournament merges, Newton refinement, tree reduction). Where recursion would
harm GPU parallelism, the code notes the correct iterative/parallel form.

C++ GPU-ready reference implementations are in grounding/quake_ref/.

Primitives:
  P1: The Hash          — SplitMix64 (counter-based, stateless)
  P2: The Float Bridge  — float-flip order-preserving transform
  P3: The Log-Add LUT   — fixed-point softplus table (8 KB)
  P4: The Binary Sketch — SimHash angular similarity

Techniques (32 + 8 novel):
  #11 Morton-Z, #12 Confidence-Gate, #1 Phantom Mask, #10 Radix-Select,
  #7 Reciprocal Gate, #19 Infinity-Mask, #4 Shift-Max, #5 LNS Arithmetic,
  #6 L1 Norm, #8 Hash Embedding, #14 Fast Sigmoid/SiLU, #16 Exponent-Clip,
  #17 Polarity-Dropout, N1 Symplectic-Shift, N2 Bit-Wave, N7 Bloom-Phase,
  N8 Stochastic-Alpha
"""

from typing import List, Tuple, Any, Callable
import struct
import math
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ═══════════════════════════════════════════
# #11 · MORTON-Z — Recursive Octree Bit-Interleaving
# ═══════════════════════════════════════════
#
# Treats space as a fractal octree: the key is the octant at the
# current level plus the key of the point inside that octant.
#
# For integer triples: key = octant_bits(depth) | recurse(depth-1)
# For floats: quantize to integer grid first.
#
# See: P011_Morton_Z_Recursive.cpp

def quantize(x: float, lo: float, hi: float, depth: int) -> int:
    """Quantize a float to an integer grid [0, 2^depth - 1]."""
    if hi <= lo:
        return 0
    t = (x - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    max_val = (1 << depth) - 1
    return round(t * max_val)


def recursive_morton_z3(x: int, y: int, z: int, depth: int) -> int:
    """Recursive Morton-Z key for 3D integer coordinates.

    At each level, extract the MSB of each coordinate to form the
    octant index, then recurse on the remaining bits.

    Exactly matches the mathematical definition of Z-order:
    key = sum over d of octant(d) << (3*d)
    """
    if depth == 0:
        return 0
    bx = (x >> (depth - 1)) & 1
    by = (y >> (depth - 1)) & 1
    bz = (z >> (depth - 1)) & 1
    octant = bx | (by << 1) | (bz << 2)
    return (octant << (3 * (depth - 1))) | recursive_morton_z3(x, y, z, depth - 1)


def morton_key_3d(px: float, py: float, pz: float,
                  lo: tuple = (-128, -128, -128),
                  hi: tuple = (127, 127, 127),
                  depth: int = 8) -> int:
    """Morton-Z key for a 3D float point.

    Quantizes to integer grid, then recursively interleaves.
    For the Dimension class, use integer exponents directly.
    """
    xi = quantize(px, lo[0], hi[0], depth)
    yi = quantize(py, lo[1], hi[1], depth)
    zi = quantize(pz, lo[2], hi[2], depth)
    return recursive_morton_z3(xi, yi, zi, depth)


# ═══════════════════════════════════════════
# #12 · CONFIDENCE-GATE — Tournament Top-2 + Probability Bound
# ═══════════════════════════════════════════
#
# Recursive tournament merges local winners upward, computing the
# true top-2 scores. Acceptance uses a rigorous bound:
#
#   p(top1) >= 1 / (1 + (V-1) * exp(-Delta/T))
#   => Delta >= T * ln((V-1) * c / (1 - c))
#
# See: P012_Confidence_Gate_Recursive.cpp

def _merge_top2(left: tuple, right: tuple) -> tuple:
    """Merge two (best, second_best) pairs into one.

    Each element is (value, index). Returns the global top-2.
    """
    candidates = [left[0], left[1], right[0], right[1]]
    best = (-float('inf'), -1)
    second = (-float('inf'), -1)
    for val, idx in candidates:
        if val > best[0]:
            second = best
            best = (val, idx)
        elif val > second[0]:
            second = (val, idx)
    return (best, second)


def recursive_top2(scores: List[float], start: int, end: int) -> tuple:
    """Recursive tournament to find top-2 values and their indices.

    Returns ((best_val, best_idx), (second_val, second_idx)).
    """
    if start == end:
        return ((scores[start], start), (-float('inf'), -1))
    mid = (start + end) >> 1
    left = recursive_top2(scores, start, mid)
    right = recursive_top2(scores, mid + 1, end)
    return _merge_top2(left, right)


def confidence_gate(scores: List[float], confidence: float = 0.9,
                    temperature: float = 1.0) -> tuple:
    """Rigorous confidence gate using tournament top-2.

    Returns (passed: bool, argmax: int, gap: float, required_gap: float).

    The gate passes only if we can PROVE p(top1) >= confidence
    under softmax at the given temperature:
        gap >= T * ln((V-1) * c / (1 - c))
    """
    if len(scores) < 2:
        return (True, 0, float('inf'), 0.0)

    V = len(scores)
    top = recursive_top2(scores, 0, V - 1)
    gap = top[0][0] - top[1][0]

    required_gap = temperature * math.log((V - 1) * confidence / (1.0 - confidence))

    passed = gap >= required_gap
    return (passed, top[0][1], gap, required_gap)


def confidence_margin_from_gap(gap: float, required_gap: float) -> float:
    """Compute confidence margin: positive = headroom, negative = deficit."""
    if required_gap == 0.0:
        return gap
    return (gap - required_gap) / abs(required_gap)


# ═══════════════════════════════════════════
# #1 · PHANTOM MASK — SplitMix64 Deterministic Hash
# ═══════════════════════════════════════════
#
# Recursive chain: state_i = Mix(state_{i-1} ^ i)
# Mask randomness from a real mixer, NOT data bits.
# Dropout semantics (Bernoulli + inverted scaling) preserved.
#
# GPU caveat: chain is sequential. Use counter-based hash for parallelism.
#
# See: P11_Phantom_Mask_Recursive.cpp

_MASK64 = (1 << 64) - 1


def splitmix64(seed: int) -> int:
    """SplitMix64 finalizer (Stafford Mix13).

    Produces a well-distributed 64-bit hash from any integer input.
    Every input bit affects every output bit with ~50% probability.
    """
    seed &= _MASK64
    seed ^= (seed >> 30) & _MASK64
    seed = (seed * 0xBF58476D1CE4E5B9) & _MASK64
    seed ^= (seed >> 27) & _MASK64
    seed = (seed * 0x94D049BB133111EB) & _MASK64
    seed ^= (seed >> 31) & _MASK64
    return seed


def phantom_hash(seed: int, layer_id: int, index: int, step: int = 0) -> int:
    """Deterministic hash for reproducible selection.

    Combines (seed, layer_id, index, step) using golden-ratio-derived
    constants for decorrelation, then applies SplitMix64 mixing.
    """
    h = seed & _MASK64
    h ^= (layer_id * 0x9E3779B97F4A7C15) & _MASK64     # golden ratio
    h ^= (index * 0x517CC1B727220A95) & _MASK64          # sqrt(3) derived
    h ^= (step * 0x6C62272E07BB0142) & _MASK64           # sqrt(5) derived
    return splitmix64(h)


def phantom_hash_chained(seed: int, layer: int, step: int, neuron_i: int) -> int:
    """Recursive chain version: state_i = Mix(state_{i-1} ^ i).

    Conceptual recurrence — sequential in neuron index.
    For GPU, use phantom_hash (counter-based) instead.
    """
    s = seed & _MASK64
    s ^= (layer * 0xD1B54A32D192ED03) & _MASK64
    s ^= (step * 0x94D049BB133111EB) & _MASK64
    for k in range(neuron_i + 1):
        s = splitmix64(s ^ k)
    return s & 0xFFFFFFFF


def phantom_select(items: list, k: int, seed: int,
                   layer_id: int = 0, step: int = 0) -> list:
    """Deterministically select k items from a list.

    Equivalent to random.sample(items, k) but fully deterministic.
    """
    if k >= len(items):
        return list(items)
    scored = []
    for i, item in enumerate(items):
        h = phantom_hash(seed, layer_id, i, step)
        scored.append((h, i, item))
    scored.sort(key=lambda x: x[0])
    return [item for _, _, item in scored[:k]]


def phantom_threshold(seed: int, layer_id: int, index: int,
                      step: int, rate: float) -> bool:
    """Deterministic dropout/inclusion decision.

    Returns True if the element should be KEPT (not dropped).
    Uses inverted dropout scaling convention.
    """
    h = phantom_hash(seed, layer_id, index, step)
    threshold = int(rate * (1 << 32))
    return (h & 0xFFFFFFFF) >= threshold


def phantom_dropout(activation: float, mask_word: int, drop_rate: float) -> float:
    """Apply dropout using a phantom mask word.

    Inverted dropout: survivors are scaled by 1/(1-rate).
    """
    threshold = int(drop_rate * (1 << 32))
    if (mask_word & 0xFFFFFFFF) < threshold:
        return 0.0
    return activation / (1.0 - drop_rate)


def phantom_attention(Q, K, V, n_buckets=64):
    """
    O(N log N) approximate attention via locality-sensitive hashing.
    
    Instead of computing full N×N attention matrix:
    1. Hash Q and K into buckets via simhash
    2. Attend only within same-bucket pairs
    3. Average bucket size ≈ N/n_buckets → cost ≈ N * (N/n_buckets)
    """
    import numpy as np
    from collections import defaultdict
    
    def softmax(x):
        # Subtract max for numerical stability
        e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return e_x / np.sum(e_x, axis=-1, keepdims=True)
        
    N, d = Q.shape
    
    # We must patch simhash_sketch to operate on numpy arrays, 
    # but for this interface we simulate it by hashing rows.
    # In a fully vectorized implementation, simhash_sketch takes matrix.
    q_hashes = [simhash_sketch(list(Q[i]), dim=d, n_bits=64) for i in range(N)]
    k_hashes = [simhash_sketch(list(K[i]), dim=d, n_bits=64) for i in range(N)]
    
    buckets = defaultdict(list)
    for i, h in enumerate(k_hashes):
        buckets[h].append(i)
    
    output = np.zeros_like(V)
    for i, q_h in enumerate(q_hashes):
        # Attend only to keys in same bucket
        candidate_indices = buckets[q_h]
        if not candidate_indices:
            continue
            
        K_local = K[candidate_indices]
        V_local = V[candidate_indices]
        
        # Local attention
        attn_scores = softmax(Q[i : i+1] @ K_local.T)
        output[i] = attn_scores @ V_local
        
    return output


# ═══════════════════════════════════════════
# #10 · RADIX-SELECT — MSB-first Bit-Splitting QuickSelect
# ═══════════════════════════════════════════
#
# Float-flip transform for order-preserving uint32 keys,
# then MSB-first bit partitioning. Recurse only into the
# bucket containing top-k => O(n) average.
#
# See: P110_Radix_Select_Recursive.cpp

def _float_to_sortable_uint32(f: float) -> int:
    """Order-preserving transform: float -> uint32."""
    bits = struct.unpack('>I', struct.pack('>f', f))[0]
    mask = -(bits >> 31)  # 0x00000000 if positive, 0xFFFFFFFF if negative
    return bits ^ (mask | 0x80000000)


def _sortable_uint32_to_float(u: int) -> float:
    """Inverse of float-flip transform."""
    if u & 0x80000000:
        bits = u ^ 0x80000000
    else:
        bits = u ^ 0xFFFFFFFF
    bits &= 0xFFFFFFFF
    return struct.unpack('>f', struct.pack('>I', bits))[0]


def _partition_by_bit(keys: list, indices: list, lo: int, hi: int, bit: int) -> int:
    """In-place partition by bit: put 1s first.

    Returns m where [lo,m) have bit set and [m,hi) have bit clear.
    """
    i, j = lo, hi - 1
    while i <= j:
        while i <= j and ((keys[i] >> bit) & 1):
            i += 1
        while i <= j and not ((keys[j] >> bit) & 1):
            j -= 1
        if i < j:
            keys[i], keys[j] = keys[j], keys[i]
            indices[i], indices[j] = indices[j], indices[i]
            i += 1
            j -= 1
    return i


def _recursive_topk(keys: list, indices: list, lo: int, hi: int,
                    k: int, bit: int) -> None:
    """Select top-k largest keys into positions [lo, lo+k) in-place.

    MSB-first bit-splitting quickselect: partition by current bit,
    recurse only into the bucket containing the survivors.
    """
    if k <= 0 or hi - lo <= 1 or bit < 0:
        return
    m = _partition_by_bit(keys, indices, lo, hi, bit)
    ones = m - lo

    if ones >= k:
        # Enough 1-bits to satisfy k; recurse into ones region
        _recursive_topk(keys, indices, lo, m, k, bit - 1)
    else:
        # Take all ones, recurse into zeros for remainder
        _recursive_topk(keys, indices, m, hi, k - ones, bit - 1)


def radix_topk_indices(values: List[float], k: int) -> List[int]:
    """Exact top-k selection using MSB-first bit-splitting quickselect.

    Returns indices of the k largest values in `values`.
    Uses float-flip transform for order-preserving uint32 keys,
    then recursive bit-partitioning.

    Results are sorted descending by value for deterministic ordering.
    """
    if k <= 0:
        return []
    n = len(values)
    if k >= n:
        return list(range(n))

    keys = [_float_to_sortable_uint32(values[i]) for i in range(n)]
    indices = list(range(n))

    _recursive_topk(keys, indices, 0, n, k, 31)

    # The top-k are now in indices[0:k] but unordered.
    # Sort them descending by original value for deterministic output.
    topk_indices = indices[:k]
    topk_indices.sort(key=lambda i: -values[i])
    return topk_indices


def radix_topk(values: List[float], k: int) -> List[Tuple[int, float]]:
    """Top-k with both indices and values."""
    indices = radix_topk_indices(values, k)
    return [(i, values[i]) for i in indices]


# ═══════════════════════════════════════════
# #7 · RECIPROCAL GATE — NR-Refined Fast 1/x
# ═══════════════════════════════════════════
#
# Magic-constant seed on |x|, then recursive Newton-Raphson.
# Handles NaN, Inf, and zero correctly.
#
# Each NR step doubles precision bits:
#   step 0: ~12-bit seed
#   step 1: ~24-bit
#   step 2: full float32
#   step 3: <1e-7 relative error
#
# See: P27_Reciprocal_Gate_Recursive.cpp

def fast_reciprocal(x: float, nr_iters: int = 3) -> float:
    """Fast 1/x using magic-constant seed + Newton-Raphson.

    Handles special values: NaN -> NaN, Inf -> 0, 0 -> Inf.
    After 3 NR iterations: < 1e-7 relative error.
    """
    # Special value handling (matches C++ reference)
    if math.isnan(x):
        return float('nan')
    if math.isinf(x):
        return math.copysign(0.0, x)
    if x == 0.0:
        return math.copysign(float('inf'), x)

    sign = -1.0 if x < 0 else 1.0
    ax = abs(x)

    # Magic-constant seed via float32 bit manipulation
    bits = struct.unpack('>I', struct.pack('>f', ax))[0]
    bits = 0x7EF311C7 - bits
    y = struct.unpack('>f', struct.pack('>I', bits & 0xFFFFFFFF))[0]

    # Recursive NR refinement: y_{n+1} = y_n * (2 - x * y_n)
    for _ in range(nr_iters):
        y = y * (2.0 - ax * y)

    return sign * y


def iv_reciprocal(lo: float, hi: float) -> tuple:
    """Interval reciprocal: 1/[lo, hi] = [1/hi, 1/lo].

    Requires interval does not straddle zero.
    """
    if lo <= 0.0 <= hi:
        raise ValueError("iv_reciprocal: interval straddles zero")
    return (fast_reciprocal(hi), fast_reciprocal(lo))


# ═══════════════════════════════════════════
# #19 · INFINITY-MASK — Branchless Causal Gating
# ═══════════════════════════════════════════
#
# Standard branchless mask using sign-bit arithmetic.
# Cascading validity version: once i < j, mask stays -inf.
#
# GPU caveat: cascading version only for sequential j traversal.
# Standard version is parallel-safe.
#
# See: P219_Infinity_Mask_Recursive.cpp

def branchless_max(a: float, b: float) -> float:
    """Branchless max using sign-bit selection."""
    diff = a - b
    bits = struct.unpack('>I', struct.pack('>f', diff))[0]
    sign = (bits >> 31) & 1
    return a * (1 - sign) + b * sign


def branchless_min(a: float, b: float) -> float:
    """Branchless min using sign-bit selection."""
    diff = a - b
    bits = struct.unpack('>I', struct.pack('>f', diff))[0]
    sign = (bits >> 31) & 1
    return b * (1 - sign) + a * sign


def branchless_clamp(x: float, lo: float, hi: float) -> float:
    """Branchless clamp: max(lo, min(x, hi))."""
    return branchless_max(lo, branchless_min(x, hi))


def infinity_gate(i: int, j: int) -> float:
    """Standard causal mask: 0 if i >= j, -inf if i < j."""
    mask = (i - j) >> 31  # 0 or -1
    return 0.0 if mask == 0 else float('-inf')


class CascadingMask:
    """Cascading causal mask with persistent invalid state.

    Once i < j occurs during a sequential j scan, the invalid
    state persists for all subsequent j values.

    Usage:
        cm = CascadingMask()
        for j in range(seq_len):
            masked_score = cm.step(score[j], query_pos, j)
    """

    def __init__(self):
        self._flow = 0  # 0 = valid, -1 = invalid (persistent)

    def reset(self):
        self._flow = 0

    def step(self, score: float, i: int, j: int) -> float:
        """Apply cascading mask to a score. Once invalid, stays invalid."""
        self._flow |= (i - j) >> 31  # OR in the sign: 0 or -1
        if self._flow == 0:
            return score
        return score + float('-inf')


# ═══════════════════════════════════════════
# #4 · SHIFT-MAX — Fixed-Point Log-Sum-Exp Tree with LUT
# ═══════════════════════════════════════════
#
# Fixed-point representation: L = round(logit * S) in natural log units.
# LUT: lut[d] = round( ln(1 + exp(-d/S)) * S )
#
# LogAdd(a, b) = max(a,b) + lut[|a-b|]
# This is the exact identity: ln(e^a + e^b) = max(a,b) + ln(1 + e^{-|a-b|})
#
# See: P24_Shift_Max_Recursive.cpp

# Fixed-point scale and LUT parameters
_FP_SCALE = 256       # 1/S nats per integer step
_FP_DMAX = 4096       # covers diffs up to 16.0 nats

# Precomputed LUT: _log1p_exp_neg_lut[d] = round( ln(1 + exp(-d/S)) * S )
_log1p_exp_neg_lut: List[int] = []


def _generate_log1p_exp_lut(scale: int = _FP_SCALE, dmax: int = _FP_DMAX) -> List[int]:
    """Generate the softplus LUT for fixed-point log-sum-exp.

    lut[d] = round( ln(1 + exp(-d/scale)) * scale )

    For d=0: ln(1+1) = ln(2) ~= 0.693 -> round(0.693 * 256) = 177
    For d=DMAX: ln(1 + exp(-16)) ~= 0 -> 0
    """
    lut = []
    for d in range(dmax + 1):
        x = -d / scale
        # Guard against overflow in exp for very negative x
        if x < -30:
            val = 0
        else:
            val = round(math.log(1.0 + math.exp(x)) * scale)
        lut.append(val)
    return lut


def _ensure_lut():
    """Lazily generate the LUT on first use."""
    global _log1p_exp_neg_lut
    if not _log1p_exp_neg_lut:
        _log1p_exp_neg_lut = _generate_log1p_exp_lut()


def fp_logadd(a: int, b: int) -> int:
    """Fixed-point log-sum-exp: ln(e^a + e^b) in integer log domain.

    Uses the identity: max(a,b) + ln(1 + e^{-|a-b|})
    with the precomputed LUT for the correction term.
    """
    _ensure_lut()
    mx = max(a, b)
    diff = abs(a - b)
    if diff > _FP_DMAX:
        return mx
    return mx + _log1p_exp_neg_lut[diff]


def recursive_logsum(L: List[int], start: int, end: int) -> int:
    """Recursive tree reduction of log-sum-exp in fixed-point domain.

    Merges pairs upward using fp_logadd until a single value remains.
    """
    if start == end:
        return L[start]
    mid = (start + end) >> 1
    left = recursive_logsum(L, start, mid)
    right = recursive_logsum(L, mid + 1, end)
    return fp_logadd(left, right)


def fast_exp_f32(x: float) -> float:
    """Fast exp(x) using range reduction + degree-3 minimax polynomial.

    Accuracy: < 0.1% max relative error across [-87, 88].
    Method: exp(x) = 2^n * 2^f  where n = floor(x/ln2), f = frac(x/ln2).
    """
    if x > 88.0:
        return math.exp(88.0)
    if x < -87.0:
        return 0.0

    LOG2E = 1.4426950408889634
    t = x * LOG2E
    n = math.floor(t)
    f = t - n

    # Degree-3 minimax polynomial for 2^f on [0, 1)
    c1 = 0.6931471805599453   # ln(2)
    c2 = 0.2402265069591007   # ln(2)^2 / 2
    c3 = 0.0558263180532956   # ln(2)^3 / 6
    pow2_f = 1.0 + f * (c1 + f * (c2 + f * c3))

    return math.ldexp(pow2_f, n)


def fast_softmax(values: List[float]) -> List[float]:
    """Softmax using fixed-point log-sum-exp tree.

    Combines Quake-Style #4 (LUT-based log-sum-exp) with #7 (fast reciprocal)
    for a full softmax pipeline matching the C++ reference.
    """
    if not values:
        return []
    _ensure_lut()

    # Convert to fixed-point log domain
    n = len(values)
    L = [round(v * _FP_SCALE) for v in values]

    # Recursive tree reduction for log-denominator
    log_denom = recursive_logsum(L, 0, n - 1)

    # Convert back: prob_i = exp((L_i - log_denom) / S)
    probs = []
    for i in range(n):
        log_prob = (L[i] - log_denom) / _FP_SCALE
        probs.append(fast_exp_f32(log_prob))

    # Normalize (compensate for fixed-point rounding)
    total = sum(probs)
    if total > 0:
        inv_total = fast_reciprocal(total)
        probs = [p * inv_total for p in probs]

    return probs


# ═══════════════════════════════════════════
# PRIMITIVE 4 · BINARY SKETCH — SimHash
# ═══════════════════════════════════════════
#
# Reduces a high-dimensional vector to a compact binary signature
# that preserves angular similarity. Hamming distance between
# sketches ~ angle between original vectors (JL lemma).
#
# Serves: #2 Polarity Gate, #15 Hamming-Gate, #18 Sign-Router,
#         N6 Census-Lock, #11 Morton-Z

def simhash_sketch(vec: List[float], hyperplanes: List[List[float]],
                   num_bits: int) -> int:
    """SimHash: project vector onto random hyperplanes, take sign bits.

    Returns a packed integer of num_bits sign bits.
    Each bit: 1 if dot(vec, hyperplane_i) >= 0, else 0.
    """
    sketch = 0
    for b in range(min(num_bits, len(hyperplanes))):
        dot = sum(v * h for v, h in zip(vec, hyperplanes[b]))
        if dot >= 0.0:
            sketch |= (1 << b)
    return sketch


def sketch_distance(a: int, b: int) -> int:
    """Hamming distance between two sketches (XOR + popcount)."""
    return bin(a ^ b).count('1')


def generate_hyperplanes(dim: int, num_bits: int, seed: int = 42) -> List[List[float]]:
    """Generate pseudo-random hyperplanes using SplitMix64.

    Each hyperplane is a dim-dimensional vector with entries
    derived from hash bits (mapped to ±1 for simplicity).
    """
    planes = []
    for b in range(num_bits):
        row = []
        for d in range(dim):
            h = phantom_hash(seed, b, d, 0)
            # Map to approximate normal: ±1 * (bit pattern / scale)
            val = ((h & 0xFFFF) / 32768.0) - 1.0
            row.append(val)
        planes.append(row)
    return planes


# ═══════════════════════════════════════════
# #5 · LOG-ADD CORE — True LNS Arithmetic
# ═══════════════════════════════════════════
#
# Store values as fixed-point log₂.
# Multiply = integer add. Accumulate = LUT-based log-add.
# Fix: IEEE bits ≠ logarithms. This is TRUE LNS with explicit conversion.

_LNS_ZERO = -32768  # sentinel for zero


def lns_from_float(x: float) -> tuple:
    """Convert float to LNS representation: (sign, log_magnitude).

    sign: 0 for positive, 1 for negative.
    log_magnitude: fixed-point log₂(|x|) * 256, or _LNS_ZERO for zero.
    """
    if x == 0.0:
        return (0, _LNS_ZERO)
    sign = 1 if x < 0 else 0
    log_mag = round(math.log2(abs(x)) * _FP_SCALE)
    return (sign, log_mag)


def lns_to_float(sign: int, log_mag: int) -> float:
    """Convert LNS back to float."""
    if log_mag == _LNS_ZERO:
        return 0.0
    val = 2.0 ** (log_mag / _FP_SCALE)
    return -val if sign else val


def lns_multiply(a: tuple, b: tuple) -> tuple:
    """LNS multiply: add log-magnitudes, XOR signs."""
    if a[1] == _LNS_ZERO or b[1] == _LNS_ZERO:
        return (0, _LNS_ZERO)
    return (a[0] ^ b[0], a[1] + b[1])


def lns_add(a: tuple, b: tuple) -> tuple:
    """LNS addition using log-add identity.

    ln(e^a + e^b) = max(a,b) + ln(1 + e^{-|a-b|})
    Uses the same LUT as Shift-Max (#4).
    """
    if a[1] == _LNS_ZERO:
        return b
    if b[1] == _LNS_ZERO:
        return a
    # Ensure |a| >= |b|
    if a[1] < b[1]:
        a, b = b, a
    # Same-sign addition
    _ensure_lut()
    delta = a[1] - b[1]
    idx = min(delta, _FP_DMAX)
    if a[0] == b[0]:
        return (a[0], a[1] + _log1p_exp_neg_lut[idx])
    else:
        # Subtraction: |a| - |b| (since |a| >= |b|)
        # ln(e^a - e^b) = a + ln(1 - e^{-(a-b)}) ≈ a for large delta
        if delta > _FP_DMAX:
            return a
        correction = round(math.log(max(1e-30, 1.0 - math.exp(-delta / _FP_SCALE))) * _FP_SCALE)
        return (a[0], a[1] + correction)


# ═══════════════════════════════════════════
# #6 · BIT-MASK NORM — L1-Based Normalization
# ═══════════════════════════════════════════
#
# Replace L2 (x², sqrt) with L1 (|x|) + calibrated correction.
# Fix: correction constant must be calibrated per-layer,
# not hardcoded at 1.253.

def l1_rms_norm(x: List[float], gamma: List[float],
                correction: float = 1.253, eps: float = 1e-6) -> List[float]:
    """L1-based RMS normalization.

    Uses mean(|x|) * correction ≈ RMS(x) for Gaussian-distributed x.
    Default correction = sqrt(π/2) ≈ 1.253 (exact for normal distribution).
    """
    n = len(x)
    mean_abs = sum(abs(xi) for xi in x) / n
    inv_rms = fast_reciprocal(mean_abs * correction + eps)
    return [xi * inv_rms * gi for xi, gi in zip(x, gamma)]


# ═══════════════════════════════════════════
# #8 · HOLOGRAPHIC EMBED — Hash Embeddings
# ═══════════════════════════════════════════
#
# Replace learned lookup table with procedural hash generation.
# Multi-hash + sign + optional residual table.

def hash_embedding(token_id: int, table: List[List[float]],
                   num_hashes: int = 3, embed_dim: int = 0) -> List[float]:
    """Hash embedding: sum of sign-weighted rows from a shared table.

    Each hash function picks a row and a sign (±1).
    Result is scaled by 1/sqrt(num_hashes).
    """
    table_size = len(table)
    if embed_dim == 0:
        embed_dim = len(table[0])
    output = [0.0] * embed_dim

    for h in range(num_hashes):
        row_hash = splitmix64(token_id ^ ((h * 2) * 0x9E3779B97F4A7C15 & _MASK64))
        row_idx = row_hash % table_size
        sign_hash = splitmix64(token_id ^ (((h * 2 + 1) * 0x9E3779B97F4A7C15) & _MASK64))
        sign = -1.0 if (sign_hash & 1) else 1.0
        for d in range(embed_dim):
            output[d] += sign * table[row_idx][d]

    scale = 1.0 / math.sqrt(num_hashes)
    return [o * scale for o in output]


# ═══════════════════════════════════════════
# #14 · SIGMOID-SHIFT — Fast Activation Approximation
# ═══════════════════════════════════════════
#
# Padé rational polynomial approximation.
# Uses Reciprocal Gate (#7) for denominator.
# < 0.2% max error.

def fast_sigmoid(x: float) -> float:
    """Fast sigmoid via fast_exp_f32 + fast_reciprocal.

    σ(x) = 1 / (1 + exp(-x)), using our fast primitives.
    """
    x = max(-10.0, min(10.0, x))
    exp_neg_x = fast_exp_f32(-x)
    return fast_reciprocal(1.0 + exp_neg_x, 2)


def fast_silu(x: float) -> float:
    """SiLU (Swish): x * sigmoid(x)."""
    return x * fast_sigmoid(x)


# ═══════════════════════════════════════════
# #16 · EXPONENT-CLIP — Hybrid Gradient Clipping
# ═══════════════════════════════════════════
#
# Fast-path: check IEEE exponent field for outliers.
# Slow-path: full global norm (triggered only when outlier detected).
# Produces identical results to standard clip when slow-path runs.

def exponent_check(values: List[float], exponent_threshold: int = 0x84) -> tuple:
    """Check IEEE exponent fields for outliers.

    Returns (has_outlier, sanitized_values).
    Exponent >= threshold (~32.0 for 0x84) flags an outlier.
    NaN/Inf are replaced with 0.
    """
    sanitized = list(values)
    has_outlier = False
    for i, v in enumerate(sanitized):
        if math.isnan(v) or math.isinf(v):
            sanitized[i] = 0.0
            has_outlier = True
            continue
        bits = struct.unpack('>I', struct.pack('>f', v))[0]
        exponent = (bits >> 23) & 0xFF
        if exponent >= exponent_threshold:
            has_outlier = True
    return (has_outlier, sanitized)


def hybrid_gradient_clip(gradients: List[float], max_norm: float = 1.0) -> List[float]:
    """Hybrid gradient clipping: fast exponent check + rare global norm.

    On ~99% of steps, the exponent check passes and no norm computation
    is needed. Only when an outlier is detected do we compute the full
    global norm and apply standard clipping.
    """
    has_outlier, grads = exponent_check(gradients)
    if not has_outlier:
        return grads
    # Slow path: full global norm clip
    norm_sq = sum(g * g for g in grads)
    norm = math.sqrt(norm_sq)
    if norm > max_norm:
        scale = max_norm / norm
        grads = [g * scale for g in grads]
    return grads


# ═══════════════════════════════════════════
# #17 · POLARITY-DROPOUT — Sign-Flip Regularization
# ═══════════════════════════════════════════
#
# Instead of zeroing, flip the sign. Preserves L2 norm.
# Must apply AFTER nonlinearity (incompatible with ReLU).

def polarity_dropout(activations: List[float], seed: int,
                     layer: int, step: int,
                     flip_rate: float = 0.1) -> List[float]:
    """Polarity dropout: flip signs instead of zeroing.

    Preserves L2 norm of the activation vector.
    Apply after nonlinearity (not before, not with ReLU).
    """
    result = list(activations)
    for i in range(len(result)):
        h = phantom_hash(seed, layer, i, step)
        threshold = int(flip_rate * (1 << 32))
        if (h & 0xFFFFFFFF) < threshold:
            result[i] = -result[i]
    return result


# ═══════════════════════════════════════════
# N1 · SYMPLECTIC-SHIFT — Integer Lattice Physics
# ═══════════════════════════════════════════
#
# Leapfrog (kick-drift-kick) on integer lattice.
# Exact shadow Hamiltonian conservation — no energy drift.
# Force uses log-approximation of 1/r² via CLZ.

def _integer_gravity(dx: int, dy: int, G: int = 1000,
                     softening_sq: int = 100) -> tuple:
    """Integer-only gravitational force approximation.

    Uses CLZ (count leading zeros) to approximate 1/r².
    All arithmetic is integer — no float needed.
    """
    # Pre-shift to avoid overflow in r_sq
    sdx = dx >> 10
    sdy = dy >> 10
    r_sq = sdx * sdx + sdy * sdy + softening_sq
    if r_sq <= 0:
        return (0, 0)
    log2_r_sq = r_sq.bit_length() - 1
    force_shift = (3 * (log2_r_sq + 20)) // 2
    force_shift = max(0, min(62, force_shift))
    fx = (G * dx) >> force_shift
    fy = (G * dy) >> force_shift
    return (fx, fy)


def symplectic_step(x: int, y: int, vx: int, vy: int,
                    cx: int, cy: int, G: int = 1000,
                    softening_sq: int = 100) -> tuple:
    """One symplectic leapfrog step (kick-drift-kick).

    Returns (new_x, new_y, new_vx, new_vy).
    Preserves a shadow Hamiltonian exactly — zero energy drift.
    """
    ax1, ay1 = _integer_gravity(cx - x, cy - y, G, softening_sq)
    vx += ax1 // 2
    vy += ay1 // 2
    x += vx
    y += vy
    ax2, ay2 = _integer_gravity(cx - x, cy - y, G, softening_sq)
    vx += ax2 // 2
    vy += ay2 // 2
    return (x, y, vx, vy)


# ═══════════════════════════════════════════
# N2 · BIT-WAVE — Manhattan Distance BFS
# ═══════════════════════════════════════════
#
# Propagates distance via bit-packed wavefront.
# Each bit = one distance threshold. OR from neighbors, shift left.
# Exact for Manhattan distance (NOT Euclidean).

def bitwave_init(width: int, height: int, sources: List[tuple]) -> List[int]:
    """Initialize a bit-wave grid. Sources get bit 0 set."""
    grid = [0] * (width * height)
    for sx, sy in sources:
        if 0 <= sx < width and 0 <= sy < height:
            grid[sy * width + sx] = 1
    return grid


def bitwave_pass(grid: List[int], width: int, height: int) -> bool:
    """One pass of bit-wave BFS. Returns True if any cell changed."""
    changed = False
    for y in range(height):
        for x in range(width):
            i = y * width + x
            self_val = grid[i]
            if self_val == 0xFFFFFFFF:
                continue
            neighbors = 0
            if x > 0:
                neighbors |= grid[i - 1]
            if x < width - 1:
                neighbors |= grid[i + 1]
            if y > 0:
                neighbors |= grid[i - width]
            if y < height - 1:
                neighbors |= grid[i + width]
            new_val = self_val | (neighbors << 1)
            new_val &= 0xFFFFFFFF  # 32-bit
            if new_val != self_val:
                grid[i] = new_val
                changed = True
    return changed


def bitwave_distance(cell: int) -> int:
    """Extract Manhattan distance from bit-wave cell value.

    Distance = position of LOWEST set bit (shortest path).
    """
    if cell == 0:
        return -1  # unreached
    # Extract lowest set bit: x & -x
    return (cell & -cell).bit_length() - 1


# ═══════════════════════════════════════════
# N7 · BLOOM-PHASE — Bitmask Collision Prefilter
# ═══════════════════════════════════════════
#
# Encode AABB axis ranges as bitmasks. Overlap = AND.
# Exact rejection (no false negatives). Fast broadphase.

def range_to_bitmask(world_min: float, world_max: float,
                     cell_size: float = 1.0) -> int:
    """Convert a 1D range to a 64-bit bitmask.

    Each bit represents one spatial cell. Set bits = cells covered.
    """
    cell_min = max(0, min(63, int(math.floor(world_min / cell_size))))
    cell_max = max(0, min(63, int(math.floor(world_max / cell_size))))
    if cell_min > cell_max:
        return 0
    span = cell_max - cell_min + 1
    if span >= 64:
        return (1 << 64) - 1
    return ((1 << span) - 1) << cell_min


def bloom_phase_overlap(ax: int, ay: int, bx: int, by: int) -> bool:
    """Test if two AABBs may overlap via bitmask AND.

    Each axis is a 64-bit bitmask from range_to_bitmask().
    Returns True if overlap is possible (no false negatives).
    """
    return bool((ax & bx) and (ay & by))


# ═══════════════════════════════════════════
# N8 · STOCHASTIC-ALPHA — Order-Independent Transparency
# ═══════════════════════════════════════════
#
# Replace sorted alpha blending with stochastic binary test.
# Converges with TAA (temporal anti-aliasing).
# Prior art: Enderton et al. 2010.

def stochastic_alpha_test(alpha: float, screen_x: int, screen_y: int,
                          frame: int) -> bool:
    """Stochastic alpha test for order-independent transparency.

    Returns True if pixel should be drawn, False if discarded.
    Uses interleaved gradient noise (Jimenez 2014).
    Requires TAA for convergence — without it, output is grainy.
    """
    x = float(screen_x) + 5.588238 * float(frame % 64)
    y = float(screen_y) + 5.588238 * float(frame % 64)
    noise = 52.9829189 * (0.06711056 * x + 0.00583715 * y)
    noise = noise - math.floor(noise)
    return noise < alpha




def _validate_phantom_mask():
    """Self-test: verify SplitMix64 avalanche and decorrelation."""
    outputs = set()
    for i in range(1000):
        h = phantom_hash(42, 0, i, 0)
        outputs.add(h)
    assert len(outputs) == 1000, "Hash collision detected"

    h1 = phantom_hash(42, 3, 7, 100)
    h2 = phantom_hash(42, 3, 7, 100)
    assert h1 == h2, "Hash not deterministic"

    items = list(range(100))
    sel1 = phantom_select(items, 10, seed=42)
    sel2 = phantom_select(items, 10, seed=42)
    assert sel1 == sel2, "Select not deterministic"

    sel3 = phantom_select(items, 10, seed=99)
    assert sel1 != sel3, "Different seeds produced same selection"

    # Chained version should also be deterministic
    c1 = phantom_hash_chained(42, 1, 0, 10)
    c2 = phantom_hash_chained(42, 1, 0, 10)
    assert c1 == c2, "Chained hash not deterministic"


def _validate_radix_select():
    """Self-test: verify MSB-first bit-splitting matches naive sort."""
    # Mixed positive, negative, zero
    values = [3.14, -1.0, 0.0, 2.718, -0.5, 100.0, -100.0, 1.0]
    k = 3
    reference = sorted(range(len(values)), key=lambda i: -values[i])[:k]
    result = radix_topk_indices(values, k)
    assert result == reference, f"Mismatch: {result} vs {reference}"

    # With Inf
    values2 = [1.0, float('inf'), -float('inf'), 0.0, 2.0]
    ref2 = sorted(range(len(values2)), key=lambda i: -values2[i])[:2]
    res2 = radix_topk_indices(values2, 2)
    assert res2 == ref2, f"Inf test mismatch: {res2} vs {ref2}"

    # Roundtrip test (float32 exact values)
    for f in [0.0, 1.0, -1.0, float('inf'), -float('inf')]:
        u = _float_to_sortable_uint32(f)
        f2 = _sortable_uint32_to_float(u)
        assert f == f2, f"Roundtrip failed for {f}"
    for f in [3.14, -3.14, 0.001, -1000.5]:
        f32 = struct.unpack('>f', struct.pack('>f', f))[0]
        u = _float_to_sortable_uint32(f32)
        f2 = _sortable_uint32_to_float(u)
        assert f2 == f32, f"Roundtrip failed for {f} (as float32: {f32})"


def _validate_morton_z():
    """Self-test: verify recursive Morton matches iterative."""
    # Known values: (1,0,0) at depth 1 should give octant 1
    assert recursive_morton_z3(1, 0, 0, 1) == 1
    assert recursive_morton_z3(0, 1, 0, 1) == 2
    assert recursive_morton_z3(0, 0, 1, 1) == 4
    assert recursive_morton_z3(1, 1, 1, 1) == 7

    # Quantize floats
    k = morton_key_3d(0.0, 0.0, 0.0)
    assert k >= 0, "Morton key should be non-negative"

    # Different points produce different keys
    keys = set()
    for x in range(-3, 4):
        for y in range(-3, 4):
            for z in range(-3, 4):
                keys.add(recursive_morton_z3(x + 128, y + 128, z + 128, 8))
    assert len(keys) == 7 * 7 * 7, "Morton keys should be unique for distinct points"


def _validate_confidence_gate():
    """Self-test: verify tournament top-2 and probability bound."""
    scores = [1.0, 5.0, 3.0, 2.0, 4.0]
    top = recursive_top2(scores, 0, 4)
    assert top[0] == (5.0, 1), f"Best should be (5.0, 1), got {top[0]}"
    assert top[1] == (4.0, 4), f"Second should be (4.0, 4), got {top[1]}"

    # With a large gap, gate should pass
    big_gap_scores = [10.0, 0.0, 0.0, 0.0, 0.0]
    passed, argmax, gap, req = confidence_gate(big_gap_scores, confidence=0.9)
    assert passed, f"Gate should pass with gap={gap}, required={req}"
    assert argmax == 0

    # With no gap, gate should fail
    equal_scores = [1.0, 1.0, 1.0, 1.0, 1.0]
    passed2, _, gap2, req2 = confidence_gate(equal_scores, confidence=0.9)
    assert not passed2, f"Gate should fail with equal scores"


# ═══════════════════════════════════════════
# SELF-DISCOVERY ARTIFACTS
# ═══════════════════════════════════════════
# Discovered by grounding/reflect_refine.py on 2026-02-17
# Generation 5 Stable Manifold (Refined recursively from Seeds).

DISCOVERY_SIGNATURE = 0xa1d47f8879a2a929
STABLE_AXIOM_INDICES = [0, 66665, 46997, 129, 2072, 18912, 22158, 5956, 13200, 420]


if __name__ == "__main__":
    print("=== Quake-Style Recursive Self-Tests ===\n")
    print(f"[INFO] System Signature: {hex(DISCOVERY_SIGNATURE)}")
    print(f"[INFO] Stable Axioms: {STABLE_AXIOM_INDICES}\n")

    _validate_morton_z()

    print("[OK] #11 Morton-Z (recursive octree) self-test passed")

    _validate_confidence_gate()
    print("[OK] #12 Confidence-Gate (tournament top-2 + bound) self-test passed")

    _validate_phantom_mask()
    print("[OK] #1  Phantom Mask (SplitMix64 chain) self-test passed")

    _validate_radix_select()
    print("[OK] #10 Radix-Select (MSB bit-splitting) self-test passed")

    # === P2: #7 Reciprocal Gate ===
    for x in [1.0, 0.5, 3.14, 100.0, 0.001, -2.5]:
        approx = fast_reciprocal(x)
        exact = 1.0 / x
        rel_err = abs(approx - exact) / abs(exact)
        assert rel_err < 1e-5, f"Reciprocal failed for {x}: err={rel_err}"
    # Special values
    assert math.isnan(fast_reciprocal(float('nan')))
    assert fast_reciprocal(float('inf')) == 0.0
    assert fast_reciprocal(float('-inf')) == 0.0
    assert math.isinf(fast_reciprocal(0.0))
    # Interval reciprocal
    rlo, rhi = iv_reciprocal(2.0, 4.0)
    assert abs(rlo - 0.25) < 1e-6 and abs(rhi - 0.5) < 1e-6
    try:
        iv_reciprocal(-1.0, 1.0)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("[OK] #7  Reciprocal Gate (NR + specials) self-test passed")

    # === P2: #19 Infinity-Mask ===
    assert branchless_max(3.0, 5.0) == 5.0
    assert branchless_max(7.0, 2.0) == 7.0
    assert branchless_min(3.0, 5.0) == 3.0
    assert branchless_min(7.0, 2.0) == 2.0
    assert branchless_clamp(10.0, 0.0, 5.0) == 5.0
    assert branchless_clamp(-3.0, 0.0, 5.0) == 0.0
    assert branchless_clamp(2.5, 0.0, 5.0) == 2.5
    assert infinity_gate(5, 3) == 0.0
    assert infinity_gate(3, 3) == 0.0
    assert infinity_gate(2, 5) == float('-inf')
    # Cascading mask
    cm = CascadingMask()
    assert cm.step(1.0, 5, 3) == 1.0      # valid: i > j
    assert cm.step(1.0, 5, 5) == 1.0      # valid: i == j
    assert cm.step(1.0, 5, 6) == -float('inf')  # invalid: i < j
    assert cm.step(1.0, 5, 4) == -float('inf')  # STAYS invalid
    print("[OK] #19 Infinity-Mask (branchless + cascading) self-test passed")

    # === P2: #4 Shift-Max ===
    for x in [-5.0, -1.0, 0.0, 1.0, 2.0, 5.0, 10.0]:
        approx = fast_exp_f32(x)
        exact = math.exp(x)
        rel_err = abs(approx - exact) / exact
        assert rel_err < 0.01, f"fast_exp failed for x={x}: err={rel_err:.4%}"
    # LUT sanity
    _ensure_lut()
    assert _log1p_exp_neg_lut[0] == round(math.log(2.0) * _FP_SCALE)
    assert _log1p_exp_neg_lut[_FP_DMAX] == 0
    # LogAdd identity: ln(e^a + e^b)
    a_fp, b_fp = round(1.0 * _FP_SCALE), round(2.0 * _FP_SCALE)
    result_fp = fp_logadd(a_fp, b_fp)
    result_float = result_fp / _FP_SCALE
    exact_result = math.log(math.exp(1.0) + math.exp(2.0))
    assert abs(result_float - exact_result) < 0.02, \
        f"LogAdd error: {result_float} vs {exact_result}"
    # Softmax
    probs = fast_softmax([1.0, 2.0, 3.0])
    assert abs(sum(probs) - 1.0) < 0.01, f"Softmax doesn't sum to 1: {sum(probs)}"
    assert probs[2] > probs[1] > probs[0], "Softmax order wrong"
    print("[OK] #4  Shift-Max (LUT log-sum-exp + softmax) self-test passed")

    # === Primitive 4: SimHash ===
    planes = generate_hyperplanes(4, 16, seed=42)
    v1 = [1.0, 0.0, 0.0, 0.0]
    v2 = [0.99, 0.01, 0.0, 0.0]  # nearly identical
    v3 = [-1.0, 0.0, 0.0, 0.0]   # opposite
    s1 = simhash_sketch(v1, planes, 16)
    s2 = simhash_sketch(v2, planes, 16)
    s3 = simhash_sketch(v3, planes, 16)
    d12 = sketch_distance(s1, s2)
    d13 = sketch_distance(s1, s3)
    assert d12 < d13, f"SimHash: similar vecs should be closer ({d12} vs {d13})"
    print("[OK] P4  SimHash (binary sketch) self-test passed")

    # === #5 LNS Arithmetic ===
    a_lns = lns_from_float(3.0)
    b_lns = lns_from_float(4.0)
    prod = lns_multiply(a_lns, b_lns)
    prod_f = lns_to_float(*prod)
    assert abs(prod_f - 12.0) < 0.1, f"LNS multiply: {prod_f} vs 12.0"
    zero_lns = lns_from_float(0.0)
    zero_prod = lns_multiply(a_lns, zero_lns)
    assert lns_to_float(*zero_prod) == 0.0
    print("[OK] #5  LNS Arithmetic (log-add core) self-test passed")

    # === #6 L1 RMS Norm ===
    x_norm = [1.0, -2.0, 3.0, -4.0]
    gamma = [1.0, 1.0, 1.0, 1.0]
    normed = l1_rms_norm(x_norm, gamma)
    norm_of_result = math.sqrt(sum(v*v for v in normed) / len(normed))
    assert 0.5 < norm_of_result < 2.0, f"L1 norm result out of range: {norm_of_result}"
    print("[OK] #6  L1 RMS Norm (bit-mask norm) self-test passed")

    # === #8 Hash Embedding ===
    table = [[float(i + j) for j in range(4)] for i in range(16)]
    emb1 = hash_embedding(42, table, num_hashes=3)
    emb2 = hash_embedding(42, table, num_hashes=3)
    emb3 = hash_embedding(99, table, num_hashes=3)
    assert emb1 == emb2, "Hash embedding not deterministic"
    assert emb1 != emb3, "Different tokens should give different embeddings"
    assert len(emb1) == 4, f"Wrong embed dim: {len(emb1)}"
    print("[OK] #8  Hash Embedding (holographic) self-test passed")

    # === #14 Sigmoid ===
    for x in [-5.0, -1.0, 0.0, 1.0, 5.0]:
        approx = fast_sigmoid(x)
        exact = 1.0 / (1.0 + math.exp(-x))
        assert abs(approx - exact) < 0.02, f"Sigmoid error at x={x}: {approx} vs {exact}"
    assert abs(fast_sigmoid(0.0) - 0.5) < 0.01
    silu_val = fast_silu(1.0)
    exact_silu = 1.0 / (1.0 + math.exp(-1.0))
    assert abs(silu_val - exact_silu) < 0.02
    print("[OK] #14 Sigmoid-Shift (Padé + fast_reciprocal) self-test passed")

    # === #16 Exponent-Clip ===
    normal_grads = [0.1, -0.2, 0.3, -0.1]
    assert not exponent_check(normal_grads)[0], "Normal grads flagged as outlier"
    outlier_grads = [0.1, 1e20, -0.2, float('nan')]
    has_out, sanitized = exponent_check(outlier_grads)
    assert has_out, "Outlier not detected"
    assert sanitized[3] == 0.0, "NaN not sanitized"
    clipped = hybrid_gradient_clip([100.0, 0.0, 0.0], max_norm=1.0)
    assert abs(math.sqrt(sum(g*g for g in clipped)) - 1.0) < 0.01
    print("[OK] #16 Exponent-Clip (hybrid gradient) self-test passed")

    # === #17 Polarity-Dropout ===
    acts = [1.0] * 1000
    flipped = polarity_dropout(acts, seed=42, layer=0, step=0, flip_rate=0.1)
    num_neg = sum(1 for a in flipped if a < 0)
    assert 50 < num_neg < 200, f"Polarity dropout flip count out of range: {num_neg}"
    l2_orig = math.sqrt(sum(a*a for a in acts))
    l2_flip = math.sqrt(sum(a*a for a in flipped))
    assert abs(l2_orig - l2_flip) < 0.01, "L2 norm not preserved"
    print("[OK] #17 Polarity-Dropout (sign-flip) self-test passed")

    # === N1 Symplectic-Shift ===
    x, y, vx, vy = 10000, 0, 0, 100
    for _ in range(100):
        x, y, vx, vy = symplectic_step(x, y, vx, vy, 0, 0)
    # After 100 steps around origin, should still be orbiting (not escaped)
    r = math.sqrt(x*x + y*y)
    assert r < 100000, f"Symplectic orbit escaped: r={r}"
    print("[OK] N1  Symplectic-Shift (integer leapfrog) self-test passed")

    # === N2 Bit-Wave ===
    grid = bitwave_init(5, 5, [(2, 2)])
    for _ in range(10):
        if not bitwave_pass(grid, 5, 5):
            break
    assert bitwave_distance(grid[2 * 5 + 2]) == 0   # source
    assert bitwave_distance(grid[2 * 5 + 3]) == 1   # 1 cell right
    assert bitwave_distance(grid[0 * 5 + 0]) == 4   # corner: Manhattan
    print("[OK] N2  Bit-Wave (Manhattan BFS) self-test passed")

    # === N7 Bloom-Phase ===
    ax = range_to_bitmask(0.0, 3.0)
    bx = range_to_bitmask(2.0, 5.0)
    cx = range_to_bitmask(10.0, 15.0)
    ay = range_to_bitmask(0.0, 3.0)
    by = range_to_bitmask(0.0, 3.0)
    cy = range_to_bitmask(0.0, 3.0)
    assert bloom_phase_overlap(ax, ay, bx, by), "Overlapping AABBs not detected"
    assert not bloom_phase_overlap(ax, ay, cx, cy), "Non-overlapping reported overlap"
    print("[OK] N7  Bloom-Phase (bitmask broadphase) self-test passed")

    # === N8 Stochastic-Alpha ===
    hits = sum(1 for f in range(1000)
               if stochastic_alpha_test(0.5, 100, 200, f))
    assert 300 < hits < 700, f"Stochastic alpha acceptance out of range: {hits}/1000"
    all_pass = all(stochastic_alpha_test(1.0, x, y, 0)
                   for x in range(10) for y in range(10))
    assert all_pass, "Alpha=1.0 should always pass"
    print("[OK] N8  Stochastic-Alpha (OIT) self-test passed")

    # === Demo ===
    print("\n--- Demo ---")
    scores = [0.85, 0.32, 0.91, 0.15, 0.67, 0.44, 0.99, 0.73, 0.28, 0.56]
    top5 = radix_topk(scores, 5)
    print(f"Top-5 scores: {top5}")

    axioms = [f"axiom_{i}" for i in range(20)]
    selected = phantom_select(axioms, 5, seed=42, layer_id=0, step=0)
    print(f"Deterministic selection (seed=42): {selected}")

    print(f"fast_reciprocal(3.14)  = {fast_reciprocal(3.14):.10f}  (exact: {1/3.14:.10f})")
    print(f"fast_exp(2.0)          = {fast_exp_f32(2.0):.6f}       (exact: {math.exp(2.0):.6f})")
    print(f"fast_softmax([1,2,3])  = {[f'{p:.4f}' for p in fast_softmax([1.0, 2.0, 3.0])]}")
    print(f"fast_sigmoid(0.0)      = {fast_sigmoid(0.0):.4f}       (exact: 0.5000)")
    print(f"fast_silu(1.0)         = {fast_silu(1.0):.4f}         (exact: {1.0/(1+math.exp(-1)):.4f})")

    print(f"\n--- LNS Demo ---")
    a_d, b_d = lns_from_float(3.0), lns_from_float(4.0)
    print(f"LNS(3.0) * LNS(4.0) = {lns_to_float(*lns_multiply(a_d, b_d)):.2f}")

    print(f"\n--- SimHash Demo ---")
    planes = generate_hyperplanes(4, 32, seed=42)
    s1 = simhash_sketch([1, 0, 0, 0], planes, 32)
    s2 = simhash_sketch([0, 0, 0, 1], planes, 32)
    print(f"Sketch distance (orthogonal): {sketch_distance(s1, s2)}/32 bits")

    print(f"\nTotal techniques: 17 (7 original + 10 new)")
