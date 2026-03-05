/**
 * P011_Morton_Z_Recursive.cpp
 * 
 * Recursive Morton-Z (Hyperspatial Bit-Interleaving)
 * 
 * Treats space as a fractal octree: the key is the octant at the
 * current level plus the key of the point inside that octant.
 * 
 * GPU note: Unroll to fixed depth (depth <= 21 for 3D uint64).
 */

#include <cstdint>
#include <cmath>

struct float3 { float x, y, z; };

__host__ __device__ inline uint32_t Quantize(float x, float lo, float hi, int depth) {
    float t = (x - lo) / (hi - lo);
    t = fminf(fmaxf(t, 0.0f), 1.0f);
    uint32_t maxv = (1u << depth) - 1u;
    return (uint32_t)lrintf(t * (float)maxv);
}

__host__ __device__ inline uint64_t RecursiveZ3(uint32_t x, uint32_t y, uint32_t z, int depth) {
    if (depth == 0) return 0ull;

    uint64_t bx = (x >> (depth - 1)) & 1ull;
    uint64_t by = (y >> (depth - 1)) & 1ull;
    uint64_t bz = (z >> (depth - 1)) & 1ull;

    uint64_t octant = (bx) | (by << 1) | (bz << 2);
    return (octant << (3 * (depth - 1))) | RecursiveZ3(x, y, z, depth - 1);
}

uint64_t MortonKey3D(float3 p, float3 lo, float3 hi, int depth) {
    uint32_t xi = Quantize(p.x, lo.x, hi.x, depth);
    uint32_t yi = Quantize(p.y, lo.y, hi.y, depth);
    uint32_t zi = Quantize(p.z, lo.z, hi.z, depth);
    return RecursiveZ3(xi, yi, zi, depth);
}
