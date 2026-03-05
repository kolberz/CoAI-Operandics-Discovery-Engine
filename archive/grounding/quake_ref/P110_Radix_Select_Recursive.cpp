/**
 * P110_Radix_Select_Recursive.cpp
 *
 * Recursive Radix-Select (MSB-first Bit-Splitting QuickSelect)
 *
 * Exact top-k selection via MSB-first bit partitioning.
 * For float inputs, apply the standard float-flip transform first
 * to get an order-preserving uint32 key.
 *
 * Recursion only continues on the survivor set -> O(n) average.
 *
 * GPU note: Implement as multi-pass radix split with prefix sums.
 */

#include <algorithm>
#include <cstdint>


// Float-flip transform: IEEE 754 float -> order-preserving uint32
inline uint32_t FloatFlip(float f) {
  uint32_t u;
  memcpy(&u, &f, sizeof(u));
  uint32_t mask = -(u >> 31); // 0x00000000 or 0xFFFFFFFF
  return u ^ (mask | 0x80000000u);
}

// In-place partition by bit: put 1s first.
// Returns m where [l,m) are ones and [m,r) are zeros.
int PartitionByBit(uint32_t *keys, int *idx, int l, int r, int bit) {
  int i = l, j = r - 1;
  while (i <= j) {
    while (i <= j && ((keys[i] >> bit) & 1u))
      i++;
    while (i <= j && !((keys[j] >> bit) & 1u))
      j--;
    if (i < j) {
      std::swap(keys[i], keys[j]);
      std::swap(idx[i], idx[j]);
    }
  }
  return i;
}

// Select top-k largest keys into the first k slots (order unspecified).
void RecursiveTopK(uint32_t *keys, int *idx, int l, int r, int k, int bit) {
  if (k <= 0 || r - l <= 1 || bit < 0)
    return;

  int m = PartitionByBit(keys, idx, l, r, bit);
  int ones = m - l;

  if (ones >= k) {
    RecursiveTopK(keys, idx, l, m, k, bit - 1);
  } else {
    RecursiveTopK(keys, idx, m, r, k - ones, bit - 1);
  }
}
