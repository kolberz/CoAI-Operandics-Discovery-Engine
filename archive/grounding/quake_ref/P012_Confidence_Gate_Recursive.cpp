/**
 * P012_Confidence_Gate_Recursive.cpp
 *
 * Recursive Confidence Gate (Tournament Top-2 + Rigorous Probability Bound)
 *
 * A recursive tournament that merges local winners upward, computing
 * the true top-2 logits. The acceptance condition uses a rigorous
 * probability lower bound under softmax at temperature T:
 *
 *   p_1 >= 1 / (1 + (V-1) * exp(-Delta/T))
 *   => Delta >= T * ln((V-1) * c / (1 - c))
 *
 * GPU note: Implement as warp/block reduction (same MergeTop2 logic).
 */

#include <cmath>
#include <cfloat>

struct Top2 {
    float a; int ia;   // best
    float b; int ib;   // second best
};

inline Top2 MergeTop2(const Top2& L, const Top2& R) {
    Top2 out{ -INFINITY, -1, -INFINITY, -1 };

    auto consider = [&](float v, int i) {
        if (v > out.a) { out.b = out.a; out.ib = out.ia; out.a = v; out.ia = i; }
        else if (v > out.b) { out.b = v; out.ib = i; }
    };

    consider(L.a, L.ia); consider(L.b, L.ib);
    consider(R.a, R.ia); consider(R.b, R.ib);
    return out;
}

Top2 RecursiveTop2(const float* logits, int start, int end) {
    if (start == end) return Top2{ logits[start], start, -INFINITY, -1 };
    int mid = (start + end) >> 1;
    Top2 L = RecursiveTop2(logits, start, mid);
    Top2 R = RecursiveTop2(logits, mid + 1, end);
    return MergeTop2(L, R);
}

// Returns true only if we can PROVE p(top1) >= conf (under softmax at temperature T).
bool RecursiveConfidenceGate(const float* logits, int V, float T, float conf, int* out_argmax) {
    Top2 t = RecursiveTop2(logits, 0, V - 1);
    float gap = t.a - t.b;

    float required_gap = T * logf(((float)(V - 1) * conf) / (1.0f - conf));
    if (gap >= required_gap) { *out_argmax = t.ia; return true; }
    return false;
}
