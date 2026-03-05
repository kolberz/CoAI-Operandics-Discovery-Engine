/**
 * P219_Infinity_Mask_Recursive.cpp
 *
 * Recursive Infinity-Mask (Branchless Causal Gating with Cascading Validity)
 *
 * Cascading validity: once i < j occurs while scanning j in increasing
 * order for a fixed query i, the invalid state persists.
 *
 * flow = 0 initially. Once i < j, flow becomes -1 and stays -1.
 * Penalty = flow & (-inf bits) = 0 or -inf.
 *
 * GPU caveat: This recurrence only makes sense for sequential j traversal
 * (CPU scan or per-thread sequential loop). For typical GPU fused attention,
 * use the standard predicated mask.
 */

#include <cstdint>

// Standard branchless mask (non-recursive, for reference)
inline float StandardCausalMask(int i, int j) {
  int32_t mask = (i - j) >> 31; // 0 or -1
  uint32_t neg_inf_bits = 0xFF800000u;
  uint32_t penalty_bits = ((uint32_t)mask) & neg_inf_bits;
  float penalty;
  __builtin_memcpy(&penalty, &penalty_bits, sizeof(float));
  return penalty;
}

// Cascading version: flow persists across sequential j scan
inline float CascadingMaskStep(float score, int i, int j, int32_t &flow) {
  flow |= (i - j) >> 31; // 0 or -1

  uint32_t neg_inf_bits = 0xFF800000u; // fp32 -inf
  uint32_t penalty_bits = ((uint32_t)flow) & neg_inf_bits;
  float penalty;
  __builtin_memcpy(&penalty, &penalty_bits, sizeof(float));

  return score + penalty;
}
