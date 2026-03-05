/**
 * P24_Shift_Max_Recursive.cpp
 *
 * Recursive Shift-Max (Fixed-Point Log-Sum-Exp Tree)
 *
 * Computes softmax denominator via a recursive log-sum-exp tree
 * in a fixed-point log domain using a precomputed LUT.
 *
 * Fixed-point representation:
 *   L = round(logit * S)  in natural log units
 *   value = L / S  nats
 *
 * LUT: lut[d] = round( ln(1 + exp(-d/S)) * S )
 *   for d = 0..DMAX
 *
 * GPU note: Implement as warp/block tree reduction with the same
 * LogAdd merge step.
 */

#include <cmath>
#include <cstdint>


// ═══════════════════════════════════════════
// LUT GENERATION
// ═══════════════════════════════════════════

constexpr int S = 256; // scale: 1/S nats per integer step
constexpr int DMAX =
    4096; // covers diffs up to 16.0 nats; beyond this, correction ~ 0

// The LUT stores: lut[d] = round( ln(1 + exp(-d/S)) * S )
// This is the "softplus" function in fixed point.
// For d=0: ln(1 + exp(0)) = ln(2) ≈ 0.6931 -> round(0.6931 * 256) = 177
// For d=DMAX: ln(1 + exp(-16)) ≈ 1.1e-7 -> 0
static int16_t kLog1pExpNeg_LUT[DMAX + 1];

void GenerateLUT() {
  for (int d = 0; d <= DMAX; ++d) {
    double x = -(double)d / (double)S;
    double val = log(1.0 + exp(x)) * (double)S;
    kLog1pExpNeg_LUT[d] = (int16_t)lround(val);
  }
}

// ═══════════════════════════════════════════
// LOG-SPACE ADD (exact identity: ln(e^a + e^b) = max(a,b) + ln(1 + e^{-|a-b|}))
// ═══════════════════════════════════════════

inline int32_t LogAdd(int32_t a, int32_t b) {
  int32_t mx = (a > b) ? a : b;
  int32_t diff = (a > b) ? (a - b) : (b - a);
  if (diff > DMAX)
    return mx;
  return mx + (int32_t)kLog1pExpNeg_LUT[diff];
}

// ═══════════════════════════════════════════
// RECURSIVE TREE REDUCTION
// ═══════════════════════════════════════════

int32_t RecursiveLogSum(const int32_t *L, int start, int end) {
  if (start == end)
    return L[start];
  int mid = (start + end) >> 1;
  int32_t left = RecursiveLogSum(L, start, mid);
  int32_t right = RecursiveLogSum(L, mid + 1, end);
  return LogAdd(left, right);
}

// ═══════════════════════════════════════════
// FULL SOFTMAX PIPELINE
// ═══════════════════════════════════════════

// Convert float logits -> fixed-point log integers
void FloatToFixedLog(const float *logits, int32_t *L, int n) {
  for (int i = 0; i < n; ++i) {
    L[i] = (int32_t)lroundf(logits[i] * (float)S);
  }
}

// Compute softmax probabilities using recursive log-sum
void FixedPointSoftmax(const float *logits, float *probs, int n) {
  int32_t *L = new int32_t[n];
  FloatToFixedLog(logits, L, n);

  int32_t log_denom = RecursiveLogSum(L, 0, n - 1);

  for (int i = 0; i < n; ++i) {
    float log_prob = (float)(L[i] - log_denom) / (float)S;
    probs[i] = expf(log_prob);
  }

  delete[] L;
}
