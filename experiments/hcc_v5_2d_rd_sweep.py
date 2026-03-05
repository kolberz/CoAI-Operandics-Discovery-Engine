"""
hcc_v5_2d_rd_sweep.py

Strict rate-distortion sweep for HCC-style predictors on a 2D image.

Key features:
- Tile-based cover (32x32 tiles, stride 16).
- H^0: 2D Polynomial surface fitting (p(u,v) = sum c_ab * u^a * v^b).
- Weighting: Separable bilinear tent weights for overlap-add.
- H^1: Affine maps (gain/bias) on horizontal/vertical tile adjacencies.
- H^2: Square Holonomy (2x2 loop obstruction) diagnostics.
- RD: Budget-targeted Δ refinement (measured in bpp - bits per pixel).

Performance optimization:
- Uses "Owner Cell" logic to avoid per-pixel Python loops during prediction.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import product
from bisect import bisect_left, insort
from typing import Dict, Iterator, List, Optional, Tuple, Literal

import numpy as np
import zlib


# ── 1) Signal (Image) generation & stress testing ───────────────────────


def make_2d_signal(
    h: int = 256,
    w: int = 256,
    *,
    seed: int = 42,
    snr_db: float = 20.0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    y_f = y / float(h)
    x_f = x / float(w)

    # Smooth base: mixture of 2D sinusoids
    clean = (
        np.sin(2 * np.pi * 2 * x_f) * np.cos(2 * np.pi * 3 * y_f) +
        0.5 * np.cos(2 * np.pi * 5 * x_f + 2 * np.pi * 2 * y_f)
    )

    # Normalize clean signal power
    clean -= clean.mean()
    clean_power = np.mean(clean**2)
    
    # Noise: Colored noise in 2D
    noise_fft = rng.normal(size=(h, w)) + 1j * rng.normal(size=(h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    dist = np.sqrt(fx**2 + fy**2)
    dist[0, 0] = 1.0
    amp = 1.0 / (dist + 0.1)**1.2
    noise = np.fft.ifft2(np.fft.fft2(noise_fft) * amp).real
    
    noise_power = np.mean(noise**2)
    target_noise_power = clean_power / (10 ** (snr_db / 10.0))
    noise *= np.sqrt(target_noise_power / max(noise_power, 1e-12))

    return (clean + noise).astype(np.float64)


def apply_photometric_drift(
    f: np.ndarray,
    tile_size: int,
    stride: int,
    *,
    bias_std: float = 0.05,
    gain_std: float = 0.02,
    seed: int = 43,
) -> np.ndarray:
    """
    Subtly modifies the image with per-tile gain/bias to see if H1 can correct it.
    We apply this to a copy of the signal.
    """
    rng = np.random.default_rng(seed)
    h, w = f.shape
    out = f.copy()
    
    # We iterate over the centers of potential tiles
    for r in range(0, h - tile_size + 1, stride):
        for c in range(0, w - tile_size + 1, stride):
            bias = rng.normal(0, bias_std)
            gain = 1.0 + rng.normal(0, gain_std)
            
            # Application with a soft window to avoid sharp discontinuities
            # though H1 is specifically designed for discontinuities.
            # Here we just apply it flatly to test H1's recovery of affine shifts.
            r_slice = slice(r, r + tile_size)
            c_slice = slice(c, c + tile_size)
            out[r_slice, c_slice] = gain * out[r_slice, c_slice] + bias
            
    return out


# ── 2) Cover + H^0 2D Polynomials ─────────────────────────────────────────


@dataclass(frozen=True)
class Tile:
    id: int
    r: int
    c: int
    h: int
    w: int


def build_tile_cover(
    img_h: int,
    img_w: int,
    *,
    tile_size: int,
    stride: int,
) -> List[Tile]:
    tiles: List[Tile] = []
    
    # Base grid
    for r in range(0, img_h - tile_size + 1, stride):
        for c in range(0, img_w - tile_size + 1, stride):
            tiles.append(Tile(len(tiles), r, c, tile_size, tile_size))
            
    # Tail row/column to ensure full coverage
    last_r = tiles[-1].r if tiles else 0
    if last_r + tile_size < img_h:
        for c in range(0, img_w - tile_size + 1, stride):
            tiles.append(Tile(len(tiles), img_h - tile_size, c, tile_size, tile_size))
            
    # Final corner if needed
    last_c = tiles[-1].c
    if last_c + tile_size < img_w:
        for r in range(0, img_h - tile_size + 1, stride):
            tiles.append(Tile(len(tiles), r, img_w - tile_size, tile_size, tile_size))
        # Ensure corner is covered if not already
        if tiles[-1].r != img_h - tile_size or tiles[-1].c != img_w - tile_size:
            tiles.append(Tile(len(tiles), img_h - tile_size, img_w - tile_size, tile_size, tile_size))
            
    return tiles


def get_poly_basis_2d(u: np.ndarray, v: np.ndarray, degree: int) -> np.ndarray:
    """ u, v are flattened coordinates in [-1, 1]. Returns [N, K] matrix. """
    basis = []
    for d in range(degree + 1):
        for i in range(d + 1):
            j = d - i
            # basis term u^i * v^j
            basis.append((u**i) * (v**j))
    return np.stack(basis, axis=1)


@dataclass(frozen=True)
class LocalPoly2D:
    tile: Tile
    degree: int
    coeffs: np.ndarray


def fit_local_polys_2d(f: np.ndarray, tiles: List[Tile], degree: int) -> List[LocalPoly2D]:
    out = []
    for t in tiles:
        tile_data = f[t.r:t.r+t.h, t.c:t.c+t.w].flatten()
        
        # Grid coords in [-1, 1]
        v_coord, u_coord = np.mgrid[0:t.h, 0:t.w]
        u = (2.0 * u_coord.flatten() / (t.w - 1)) - 1.0
        v = (2.0 * v_coord.flatten() / (t.h - 1)) - 1.0
        
        basis = get_poly_basis_2d(u, v, degree)
        # Solve least squares
        coeffs, _, _, _ = np.linalg.lstsq(basis, tile_data, rcond=None)
        out.append(LocalPoly2D(t, degree, coeffs))
    return out


def eval_tile_poly(p: LocalPoly2D) -> np.ndarray:
    t = p.tile
    v_coord, u_coord = np.mgrid[0:t.h, 0:t.w]
    u = (2.0 * u_coord.flatten() / (t.w - 1)) - 1.0
    v = (2.0 * v_coord.flatten() / (t.h - 1)) - 1.0
    basis = get_poly_basis_2d(u, v, p.degree)
    return (basis @ p.coeffs).reshape((t.h, t.w))


# ── 3) H^1 Affine Maps (2D Adjacency) ─────────────────────────────────────


@dataclass(frozen=True)
class AffineMap:
    a: float
    b: float
    rms_fit: float

    def __call__(self, y: np.ndarray) -> np.ndarray:
        return self.a * y + self.b

    def compose(self, other: AffineMap) -> AffineMap:
        return AffineMap(self.a * other.a, self.a * other.b + self.b, 0.0)


def fit_affine_2d(y1: np.ndarray, y2: np.ndarray) -> AffineMap:
    """ Fits g(y1) -> y2. """
    y1_f = y1.flatten()
    y2_f = y2.flatten()
    if y1_f.size == 0: return AffineMap(1, 0, 0)
    
    A = np.stack([y1_f, np.ones_like(y1_f)], axis=1)
    # Ridge solve
    reg = 1e-6 * np.eye(2)
    sol, _, _, _ = np.linalg.lstsq(A.T @ A + reg, A.T @ y2_f, rcond=None)
    a, b = float(sol[0]), float(sol[1])
    
    rmse = np.sqrt(np.mean((a*y1_f + b - y2_f)**2))
    return AffineMap(a, b, float(rmse))


def build_h1_2d(polys: List[LocalPoly2D], tiles: List[Tile]) -> Dict[Tuple[int, int], AffineMap]:
    """ Fits maps between horizontal and vertical adjacent tiles. """
    h1 = {}
    tile_map = {(t.r, t.c): t.id for t in tiles}
    
    precomputed_vals = [eval_tile_poly(p) for p in polys]

    for t in tiles:
        # Check Right neighbor
        r_id = tile_map.get((t.r, t.c + 16)) # fixed stride 16 for now
        if r_id is not None:
            # Overlap is t.c+16 to t.c+32
            # Relative to t: c=16:32. Relative to r: c=0:16.
            y_t = precomputed_vals[t.id][:, 16:32]
            y_r = precomputed_vals[r_id][:, 0:16]
            h1[(r_id, t.id)] = fit_affine_2d(y_r, y_t)
            
        # Check Down neighbor
        d_id = tile_map.get((t.r + 16, t.c))
        if d_id is not None:
            # Overlap is t.r+16 to t.r+32
            y_t = precomputed_vals[t.id][16:32, :]
            y_d = precomputed_vals[d_id][0:16, :]
            h1[(d_id, t.id)] = fit_affine_2d(y_d, y_t)
            
    return h1


# ── 4) Prediction (Owner-Cell Optimized) ──────────────────────────────────


@dataclass(frozen=True)
class Owners:
    """ Precomputed owner cells for fast OAA. """
    tile_indices_per_pixel: List[Tuple[int, ...]]


def build_owner_map(h: int, w: int, tiles: List[Tile]) -> List[Tuple[int, ...]]:
    owners = [[] for _ in range(h * w)]
    for t in tiles:
        for r in range(t.r, t.r + t.h):
            for c in range(t.c, t.c + t.w):
                owners[r * w + c].append(t.id)
    return [tuple(o) for o in owners]


@dataclass(frozen=True)
class Predictors2D:
    pred_base: np.ndarray
    pred_avg: np.ndarray
    pred_topo: np.ndarray
    corr_topo: np.ndarray


def predict_all_2d(
    img_h: int,
    img_w: int,
    tiles: List[Tile],
    polys: List[LocalPoly2D],
    h1: Dict[Tuple[int, int], AffineMap],
) -> Predictors2D:
    """ Vectorized OAA prediction using owner cells. """
    pred_base = np.zeros((img_h, img_w))
    pred_avg = np.zeros((img_h, img_w))
    pred_topo = np.zeros((img_h, img_w))
    
    # Tent weights (32x32) - use narrow range to avoid zeros at exactly -1, 1
    # We want weight to be 0 at the boundary of the tile's 'potential' reach, 
    # but strictly positive within the 32x32 grid.
    eps = 1e-6
    phi = 1.0 - np.abs(np.linspace(-1 + eps, 1 - eps, 32))
    weights_2d = phi[:, None] * phi[None, :]
    
    precomputed_vals = [eval_tile_poly(p) for p in polys]
    
    # 1. BASE: Simple local ownership (owner of top-left corner index)
    for t in tiles:
        pred_base[t.r:t.r+t.h, t.c:t.c+t.w] = precomputed_vals[t.id]

    # 2. AVG and TOPO: Grid of 16x16 cells
    stride = 16
    for r_base in range(0, img_h, stride):
        for c_base in range(0, img_w, stride):
            r_end = min(r_base + stride, img_h)
            c_end = min(c_base + stride, img_w)
            if r_end <= r_base or c_end <= c_base: continue
            
            covering_ids = []
            for t in tiles:
                if t.r <= r_base and t.r + t.h >= r_end and \
                   t.c <= c_base and t.c + t.w >= c_end:
                    covering_ids.append(t.id)
            
            if not covering_ids: continue
            
            cell_slice = (slice(r_base, r_end), slice(c_base, c_end))
            
            # AVG
            acc_v = np.zeros((r_end - r_base, c_end - c_base))
            acc_w = np.zeros_like(acc_v)
            for tid in covering_ids:
                t = tiles[tid]
                dr, dc = r_base - t.r, c_base - t.c
                w = weights_2d[dr : dr + (r_end - r_base), dc : dc + (c_end - c_base)]
                v = precomputed_vals[tid][dr : dr + (r_end - r_base), dc : dc + (c_end - c_base)]
                acc_v += v * w
                acc_w += w
            
            # Division safeguard
            acc_w[acc_w < 1e-12] = 1.0
            pred_avg[cell_slice] = acc_v / acc_w
            
            # TOPO
            base_id = covering_ids[0]
            acc_v_topo = np.zeros_like(acc_v)
            for tid in covering_ids:
                t = tiles[tid]
                dr, dc = r_base - t.r, c_base - t.c
                w = weights_2d[dr : dr + (r_end - r_base), dc : dc + (c_end - c_base)]
                v = precomputed_vals[tid][dr : dr + (r_end - r_base), dc : dc + (c_end - c_base)]
                
                if tid == base_id:
                    mapped = v
                else:
                    g = h1.get((tid, base_id))
                    if g:
                        mapped = g.a * v + g.b
                    else:
                        mapped = v
                acc_v_topo += mapped * w
            pred_topo[cell_slice] = acc_v_topo / acc_w

    corr_topo = pred_topo - pred_base
    return Predictors2D(pred_base, pred_avg, pred_topo, corr_topo)


# ── 5) H^2 Square Holonomy ──────────────────────────────────────────────


def compute_square_holonomy(
    tiles: List[Tile],
    polys: List[LocalPoly2D],
    h1: Dict[Tuple[int, int], AffineMap],
) -> List[float]:
    """ Measures loop obstruction on 4-way overlaps. """
    tile_grid = {}
    for t in tiles:
        tile_grid[(t.r, t.c)] = t.id
        
    holonomies = []
    precomputed_vals = [eval_tile_poly(p) for p in polys]
    
    for (r, c), a_id in tile_grid.items():
        # Check for 2x2 block
        b_id = tile_grid.get((r, c + 16))
        c_id = tile_grid.get((r + 16, c))
        d_id = tile_grid.get((r + 16, c + 16))
        
        if all(x is not None for x in [b_id, c_id, d_id]):
            # 4-way overlap is (r+16:r+32, c+16:c+32)
            # Center of D corresponds to (0:16, 0:16) in D
            p_d = precomputed_vals[d_id][0:16, 0:16]
            
            # Path 1: D -> B -> A
            g_db = h1.get((d_id, b_id))
            g_ba = h1.get((b_id, a_id))
            
            # Path 2: D -> C -> A
            g_dc = h1.get((d_id, c_id))
            g_ca = h1.get((c_id, a_id))
            
            if all(g is not None for g in [g_db, g_ba, g_dc, g_ca]):
                v1 = g_ba(g_db(p_d))
                v2 = g_ca(g_dc(p_d))
                err = np.sqrt(np.mean((v1 - v2)**2))
                holonomies.append(float(err))
                
    return holonomies


# ── 6) RD and Experiment Logic ──────────────────────────────────────────


def shannon_entropy_int(q: np.ndarray) -> float:
    flat = q.ravel()
    if flat.size == 0: return 0.0
    _, counts = np.unique(flat, return_counts=True)
    probs = counts / flat.size
    return -np.sum(probs * np.log2(probs))


@dataclass(frozen=True)
class RDPoint:
    bpp: float
    rmse: float
    delta: float


def eval_rd_2d(x: np.ndarray, overhead_bits: int, delta: float) -> RDPoint:
    q = np.round(x / delta).astype(np.int32)
    H = shannon_entropy_int(q)
    bits = overhead_bits + 32 + int(np.ceil(H * x.size))
    return RDPoint(bpp=bits / x.size, rmse=np.sqrt(np.mean((x - q*delta)**2)), delta=delta)


def rd_frontier_refined(x: np.ndarray, overhead_bits: int, target_bpps: List[float]) -> List[RDPoint]:
    sigma = np.std(x)
    sigma = max(sigma, 1e-12)
    
    # 1. Initial grid
    deltas = sigma * np.logspace(-3, 1, 60)
    pts = [eval_rd_2d(x, overhead_bits, d) for d in deltas]
    
    # 2. Refine locally around target_bpps
    for _ in range(2):
        pts.sort(key=lambda p: p.bpp)
        new_deltas = []
        for target in target_bpps:
            below, above = None, None
            for p in pts:
                if p.bpp <= target: below = p
                else:
                    above = p
                    break
            if below and above:
                dlo, dhi = min(below.delta, above.delta), max(below.delta, above.delta)
                grid = np.exp(np.linspace(np.log(dlo), np.log(dhi), 12))[1:-1]
                new_deltas.extend(grid)
        
        if not new_deltas: break
        pts.extend([eval_rd_2d(x, overhead_bits, d) for d in new_deltas])

    # Pareto
    pts.sort(key=lambda p: p.bpp)
    frontier = []
    min_rmse = 1e18
    for p in pts:
        if p.rmse < min_rmse:
            frontier.append(p)
            min_rmse = p.rmse
    return frontier


def best_at_bpp(frontier: List[RDPoint], target: float) -> Optional[RDPoint]:
    best = None
    for p in frontier:
        if p.bpp <= target:
            best = p
        else:
            break
    return best


def run_2d_experiment():
    H, W = 256, 256
    tile_size = 32
    stride = 16
    degrees = [1, 2, 4, 8]
    
    img = make_2d_signal(H, W)
    # Stress test: Apply drift
    # bias_std=0.1 is quite strong for a [ -1, 1 ] signal!
    drift_img = apply_photometric_drift(img, tile_size, stride, bias_std=0.1, gain_std=0.04)
    
    tiles = build_tile_cover(H, W, tile_size=tile_size, stride=stride)
    
    print(f"2D Image Analysis: {H}x{W} signal.")
    print(f"Cover: {len(tiles)} tiles of size {tile_size}, stride {stride}.\n")
    
    target_bpps = [0.25, 0.5, 1.0, 2.0]

    for deg in degrees:
        polys = fit_local_polys_2d(drift_img, tiles, deg)
        h1 = build_h1_2d(polys, tiles)
        preds = predict_all_2d(H, W, tiles, polys, h1)
        
        holonomies = compute_square_holonomy(tiles, polys, h1)
        h2_rms = np.mean(holonomies) if holonomies else 0.0
        
        coeff_bits = 16
        k = (deg + 1) * (deg + 2) // 2
        h0_bits = len(tiles) * k * coeff_bits
        h1_bits = len(h1) * 2 * 16 # gain + bias
        
        overhead_base = 128 + h0_bits
        overhead_topo = 128 + h0_bits + h1_bits
        
        r_base = img - preds.pred_base
        r_avg = img - preds.pred_avg
        r_topo = img - preds.pred_topo
        
        f_base = rd_frontier_refined(r_base, overhead_base, target_bpps)
        f_avg = rd_frontier_refined(r_avg, overhead_base, target_bpps)
        f_topo = rd_frontier_refined(r_topo, overhead_topo, target_bpps)
        
        print(f"deg={deg} (k={k})")
        print(f"  H2 RMS: {h2_rms:.3e}")
        print(f"  RMSE at budgets (bpp):")
        for b in target_bpps:
            pb = best_at_bpp(f_base, b)
            pa = best_at_bpp(f_avg, b)
            pt = best_at_bpp(f_topo, b)
            
            rb = pb.rmse if pb else float("nan")
            ra = pa.rmse if pa else float("nan")
            rt = pt.rmse if pt else float("nan")
            print(f"    {b:.2f} bpp: {rb:.2e} / {ra:.2e} / {rt:.2e}")
        print()


if __name__ == "__main__":
    run_2d_experiment()
