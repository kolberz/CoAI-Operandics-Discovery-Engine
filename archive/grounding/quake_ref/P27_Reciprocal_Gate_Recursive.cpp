/**
 * P27_Reciprocal_Gate_Recursive.cpp
 *
 * Recursive Reciprocal Gate (Magic-Constant Seed + Newton-Raphson)
 *
 * Magic constant seed on |x|, then recursive Newton-Raphson refinement.
 * Handles special values: NaN, Inf, 0.
 *
 * Each NR step doubles precision bits:
 *   step 0: ~12-bit seed
 *   step 1: ~24-bit
 *   step 2: full float32 precision
 */

#include <cmath>
#include <cstdint>

float RecursiveInverse(float x, int steps) {
  if (isnan(x))
    return NAN;
  if (isinf(x))
    return copysignf(0.0f, x);
  if (x == 0.0f)
    return copysignf(INFINITY, x);

  float ax = fabsf(x);

  // Seed: interpret bits of ax
  uint32_t i = *reinterpret_cast<uint32_t *>(&ax);
  uint32_t ybits = 0x7EF311C7u - i;
  float y = *reinterpret_cast<float *>(&ybits);

  // Recursive refinement (conceptually recursive; implement as unrolled loop)
  for (int s = 0; s < steps; ++s) {
    y = y * (2.0f - ax * y);
  }
  return copysignf(y, x);
}
