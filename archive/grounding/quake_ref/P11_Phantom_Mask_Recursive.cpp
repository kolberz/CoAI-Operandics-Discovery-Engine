/**
 * P11_Phantom_Mask_Recursive.cpp
 *
 * Recursive Phantom Mask (Intrinsic Bitwise Dropout)
 *
 * Mask state at neuron i is derived from neuron i-1 via SplitMix64
 * chaining. Uses activation values ONLY for scaling, NOT for randomness.
 *
 * GPU caveat: A strict chain is sequential. Implement via counter-based
 * hashing (non-recursive) or blockwise scans for parallelism.
 */

#include <cstdint>

// SplitMix64 finalizer (good avalanche)
inline uint64_t Mix(uint64_t x) {
  x += 0x9E3779B97F4A7C15ull;
  x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
  x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
  return x ^ (x >> 31);
}

// Conceptual recurrence: state_i = Mix(state_{i-1} ^ i)
// Implement as a small scan within a block, or replace with counter-based hash.
uint32_t RecursiveMaskWord(uint64_t seed, int layer, int step, int neuron_i) {
  uint64_t s = seed ^ (uint64_t)layer * 0xD1B54A32D192ED03ull ^
               (uint64_t)step * 0x94D049BB133111EBull;

  // Conceptual recursion (sequential).
  // Do not do this literally for large neuron_i on GPU.
  for (int k = 0; k <= neuron_i; ++k)
    s = Mix(s ^ (uint64_t)k);

  return (uint32_t)s;
}

float RecursiveDropout(float activation, uint32_t r, float drop_rate) {
  uint32_t threshold = (uint32_t)(drop_rate * 4294967296.0f);
  if (r < threshold)
    return 0.0f;
  return activation / (1.0f - drop_rate); // inverted dropout scaling
}
