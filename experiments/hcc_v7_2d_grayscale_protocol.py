"""
hcc_v7_2d_grayscale_protocol.py

Fixes the issues identified in the review:
(1) Root base out-of-support bug resolved.
(2) Added pearson_corr().
(3) Chart drift contamination removed.
(4) Added positive-control warning for chart drift.
(5) Generalized covering_tiles_for_cell().
(6) Uses deque for BFS.
(7) Prints both conservative and inverse-derived H1 overheads.
(8) Reports predRMSE and rho_d.

Everything else from v7 remains: full factorial, RD refinement, layered coders, δ_corr, τ*, diff spectrum,
H2 rho_d and censored beta, slope and tree-depth diagnostics.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Literal, Optional, Tuple

import numpy as np


# =============================================================================
# Experiment defaults
# =============================================================================

BaseStrategy = Literal["owner", "root"]
Transport = Literal["local", "tree"]
Weighting = Literal["uniform", "tent"]
Drift = Literal["none", "field", "chart"]
PolyBasis = Literal["total", "tensor"]

H = W = 256
P = 32
S = 16

DEGREES = [1, 2, 3, 5]
BUDGETS_BPP = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]

BASE_STRATEGIES: list[BaseStrategy] = ["owner", "root"]
WEIGHTINGS: list[Weighting] = ["uniform", "tent"]
TRANSPORTS: list[Transport] = ["local", "tree"]
DRIFTS: list[Drift] = ["none", "field", "chart"]

POLY_BASIS: PolyBasis = "total"

COEFF_BITS = 16
AFFINE_BITS = 16
CONTAINER_BITS = 128
DELTA_BITS = 32
ENTROPY_MODEL_OVERHEAD_BITS = 0

INITIAL_N = 70
REFINE_ROUNDS = 2
REFINE_PTS_PER_BUDGET = 20

LAYER_DC = 30
LAYER_DR = 40

H2_NOISE_FLOOR_ABS = 1e-12

CHART_SIGMA_A = 0.10
CHART_SIGMA_B = 0.05
CHART_SEED = 1
ROOT_TILE_IDX = 0

LOW_FREQ_FRAC = 0.25

# Positive control configuration (what “should” work if H1 instrument is correct):
# Root gauge + tree transport is the cleanest “global calibration” setting.
POSCTRL_BASE: BaseStrategy = "root"
POSCTRL_TR: Transport = "tree"
POSCTRL_W: Weighting = "tent"
POSCTRL_MARGIN = 0.0  # warn if rmse_topo_pred >= rmse_avg_pred + margin


# =============================================================================
# RD utilities
# =============================================================================

@dataclass(frozen=True)
class RDPoint:
    bits_total: int
    rmse: float
    delta: float


def quantize_step(x: np.ndarray, delta: float) -> tuple[np.ndarray, np.ndarray]:
    if not np.isfinite(delta) or delta <= 0.0:
        raise ValueError(f"delta must be finite and > 0, got {delta}")
    q = np.rint(x / delta).astype(np.int64)
    xhat = q.astype(float) * delta
    return q, xhat


def entropy_int_symbols(q: np.ndarray) -> float:
    flat = np.asarray(q, dtype=np.int64).ravel()
    if flat.size == 0:
        return 0.0

    qmin = int(flat.min())
    qmax = int(flat.max())
    rng = qmax - qmin + 1

    if rng <= 200_000:
        counts = np.bincount((flat - qmin).astype(np.int64), minlength=rng).astype(float)
        p = counts[counts > 0] / float(flat.size)
        return float(-(p * np.log2(p)).sum())

    _, counts = np.unique(flat, return_counts=True)
    p = counts.astype(float) / float(flat.size)
    return float(-(p * np.log2(p)).sum())


def make_delta_sweep(x: np.ndarray, n: int) -> np.ndarray:
    sigma = float(np.std(x))
    sigma = max(sigma, 1e-12)
    dmin = sigma / 512.0
    dmax = sigma * 8.0
    return dmin * (dmax / dmin) ** np.linspace(0.0, 1.0, n)


def eval_rd_point(
    x: np.ndarray,
    *,
    overhead_bits: int,
    delta: float,
    delta_bits: int,
    entropy_overhead_bits: int,
) -> RDPoint:
    q, xhat = quantize_step(x, delta)
    H = entropy_int_symbols(q)
    bits = overhead_bits + delta_bits + int(np.ceil(H * x.size)) + entropy_overhead_bits
    rmse_err = float(np.sqrt(np.mean((x - xhat) ** 2)))
    return RDPoint(bits_total=bits, rmse=rmse_err, delta=float(delta))


def pareto_frontier(points: list[RDPoint]) -> list[RDPoint]:
    if not points:
        return []
    pts = sorted(points, key=lambda p: (p.bits_total, p.rmse))
    out: list[RDPoint] = []
    best_rmse = float("inf")
    last_bits: Optional[int] = None
    for p in pts:
        if last_bits is not None and p.bits_total == last_bits:
            continue
        if p.rmse < best_rmse - 1e-15:
            out.append(p)
            best_rmse = p.rmse
            last_bits = p.bits_total
    return out


def best_at_budget(frontier: list[RDPoint], budget_bits: int) -> Optional[RDPoint]:
    best = None
    for p in frontier:
        if p.bits_total <= budget_bits:
            best = p
        else:
            break
    return best


def rd_frontier_budget_refined(
    x: np.ndarray,
    *,
    overhead_bits: int,
    budgets_bits: list[int],
    delta_bits: int,
    entropy_overhead_bits: int,
    initial_n: int,
    refine_rounds: int,
    refine_pts_per_budget: int,
) -> list[RDPoint]:
    x = np.asarray(x, dtype=float)
    init = [float(d) for d in make_delta_sweep(x, initial_n) if np.isfinite(d) and d > 0]
    pts_by_delta: dict[float, RDPoint] = {}

    def eval_many(deltas: Iterable[float]) -> None:
        for d in deltas:
            if d in pts_by_delta:
                continue
            pts_by_delta[d] = eval_rd_point(
                x,
                overhead_bits=overhead_bits,
                delta=d,
                delta_bits=delta_bits,
                entropy_overhead_bits=entropy_overhead_bits,
            )

    eval_many(init)

    for _ in range(refine_rounds):
        pts_sorted = sorted(pts_by_delta.values(), key=lambda p: p.bits_total)
        new_deltas: list[float] = []

        for B in budgets_bits:
            below = None
            above = None
            for p in pts_sorted:
                if p.bits_total <= B:
                    below = p
                else:
                    above = p
                    break
            if below is None or above is None:
                continue
            d0, d1 = below.delta, above.delta
            if d0 <= 0 or d1 <= 0 or d0 == d1:
                continue
            lo, hi = (d0, d1) if d0 < d1 else (d1, d0)
            grid = np.exp(np.linspace(np.log(lo), np.log(hi), refine_pts_per_budget + 2))[1:-1]
            new_deltas.extend(float(g) for g in grid)

        new_ds = [d for d in new_deltas if np.isfinite(d) and d > 0 and d not in pts_by_delta]
        if not new_ds:
            break
        eval_many(new_ds)

    return pareto_frontier(list(pts_by_delta.values()))


def rd_two_stage(
    *,
    target: np.ndarray,
    pred_base: np.ndarray,
    corr_true: np.ndarray,
    overhead_bits: int,
    delta_bits: int,
    entropy_overhead_bits: int,
    n_dc: int,
    n_dr: int,
) -> list[RDPoint]:
    t = target.reshape(-1).astype(float)
    b = pred_base.reshape(-1).astype(float)
    c = corr_true.reshape(-1).astype(float)
    n = t.size

    points: list[RDPoint] = []
    deltas_c = make_delta_sweep(c, n_dc)

    for dc in deltas_c:
        dc = float(dc)
        if not np.isfinite(dc) or dc <= 0:
            continue
        qc, c_hat = quantize_step(c, dc)
        Hc = entropy_int_symbols(qc)
        bits_c = delta_bits + int(np.ceil(Hc * n)) + entropy_overhead_bits

        stage1 = b + c_hat
        r = t - stage1
        deltas_r = make_delta_sweep(r, n_dr)

        for dr in deltas_r:
            dr = float(dr)
            if not np.isfinite(dr) or dr <= 0:
                continue
            qr, r_hat = quantize_step(r, dr)
            Hr = entropy_int_symbols(qr)
            bits_r = delta_bits + int(np.ceil(Hr * n)) + entropy_overhead_bits

            recon = stage1 + r_hat
            rmse_val = float(np.sqrt(np.mean((recon - t) ** 2)))
            points.append(RDPoint(bits_total=overhead_bits + bits_c + bits_r, rmse=rmse_val, delta=dr))

    return pareto_frontier(points)


# =============================================================================
# Geometry: tiles and overlaps
# =============================================================================

@dataclass(frozen=True)
class Tile:
    idx: int
    gx: int
    gy: int
    x0: int
    y0: int


def build_tiles(H: int, W: int, P: int, S: int) -> tuple[list[Tile], tuple[int, int], list[int], list[int]]:
    xs = list(range(0, W - P + 1, S))
    ys = list(range(0, H - P + 1, S))
    if xs[-1] != W - P:
        xs.append(W - P)
    if ys[-1] != H - P:
        ys.append(H - P)
    nx, ny = len(xs), len(ys)

    tiles: list[Tile] = []
    idx = 0
    for gy, y0 in enumerate(ys):
        for gx, x0 in enumerate(xs):
            tiles.append(Tile(idx=idx, gx=gx, gy=gy, x0=x0, y0=y0))
            idx += 1
    return tiles, (nx, ny), xs, ys


def overlap_slices(a: Tile, b: Tile, P: int) -> Optional[tuple[tuple[slice, slice], tuple[slice, slice]]]:
    s_x = max(a.x0, b.x0); e_x = min(a.x0 + P, b.x0 + P)
    s_y = max(a.y0, b.y0); e_y = min(a.y0 + P, b.y0 + P)
    if s_x >= e_x or s_y >= e_y:
        return None
    sa = (slice(s_y - a.y0, e_y - a.y0), slice(s_x - a.x0, e_x - a.x0))
    sb = (slice(s_y - b.y0, e_y - b.y0), slice(s_x - b.x0, e_x - b.x0))
    return sa, sb


def tent_weights(P: int) -> np.ndarray:
    u = np.linspace(-1.0, 1.0, P) if P > 1 else np.array([0.0])
    w = 1.0 - np.abs(u)
    return np.outer(w, w).astype(float)


# =============================================================================
# H0: polynomial surface per tile
# =============================================================================

def exps_total(deg: int) -> list[tuple[int, int]]:
    exps = []
    for a in range(deg + 1):
        for b in range(deg + 1 - a):
            exps.append((a, b))
    return exps


def exps_tensor(deg: int) -> list[tuple[int, int]]:
    return [(a, b) for a in range(deg + 1) for b in range(deg + 1)]


def poly_basis(P: int, deg: int, basis: PolyBasis) -> tuple[np.ndarray, int]:
    u = np.linspace(-1.0, 1.0, P) if P > 1 else np.array([0.0])
    X, Y = np.meshgrid(u, u, indexing="xy")
    exps = exps_total(deg) if basis == "total" else exps_tensor(deg)
    Phi = np.stack([(X**a) * (Y**b) for (a, b) in exps], axis=-1).reshape(P * P, -1)
    return Phi, Phi.shape[1]


def ridge_pinv(Phi: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    A = Phi.T @ Phi + ridge * np.eye(Phi.shape[1])
    return np.linalg.solve(A, Phi.T)


def fit_h0_poly_tiles_from_image(
    img_for_fit: np.ndarray,
    tiles: list[Tile],
    P: int,
    deg: int,
    basis: PolyBasis,
) -> tuple[list[np.ndarray], int]:
    Phi, K = poly_basis(P, deg, basis)
    Pmat = ridge_pinv(Phi)
    preds: list[np.ndarray] = []
    for t in tiles:
        patch = img_for_fit[t.y0:t.y0 + P, t.x0:t.x0 + P]
        y = patch.reshape(-1)
        c = Pmat @ y
        yhat = (Phi @ c).reshape(P, P)
        preds.append(yhat)
    return preds, K


def fit_h0_poly_tiles_from_patches(
    patches: list[np.ndarray],
    P: int,
    deg: int,
    basis: PolyBasis,
) -> tuple[list[np.ndarray], int]:
    Phi, K = poly_basis(P, deg, basis)
    Pmat = ridge_pinv(Phi)
    preds: list[np.ndarray] = []
    for patch in patches:
        y = patch.reshape(-1)
        c = Pmat @ y
        yhat = (Phi @ c).reshape(P, P)
        preds.append(yhat)
    return preds, K


# =============================================================================
# H1: affine maps on overlaps
# =============================================================================

@dataclass(frozen=True)
class Affine:
    a: float
    b: float

    def __call__(self, y: np.ndarray) -> np.ndarray:
        return self.a * y + self.b

    def compose(self, other: "Affine") -> "Affine":
        return Affine(self.a * other.a, self.a * other.b + self.b)

    def inv(self, eps: float = 1e-9) -> "Affine":
        if abs(self.a) < eps:
            return Affine(1.0, -self.b)
        ia = 1.0 / self.a
        return Affine(ia, -self.b * ia)


def fit_affine(
    x: np.ndarray,
    y: np.ndarray,
    ridge_rel: float = 1e-4,
    ridge_abs: float = 1e-9,
    cond_fallback: float = 1e8,
) -> Affine:
    x = x.reshape(-1).astype(float)
    y = y.reshape(-1).astype(float)
    if x.size == 0:
        return Affine(1.0, 0.0)

    X = np.stack([x, np.ones_like(x)], axis=1)
    XtX = X.T @ X
    lam = ridge_abs + ridge_rel * max(float(np.trace(XtX) / 2.0), 1e-12)
    XtXr = XtX + lam * np.eye(2)

    cond = float(np.linalg.cond(XtXr))
    if not np.isfinite(cond) or cond > cond_fallback:
        b_val = float(np.mean(y - x))
        return Affine(1.0, b_val)

    a, b_val = np.linalg.solve(XtXr, X.T @ y)
    return Affine(float(a), float(b_val))


def build_h1_all_adj(
    preds: list[np.ndarray],
    tiles: list[Tile],
    grid: tuple[int, int],
    P: int,
) -> dict[tuple[int, int], Affine]:
    nx, ny = grid
    by_grid = {(t.gx, t.gy): t.idx for t in tiles}
    h1: dict[tuple[int, int], Affine] = {}

    for t in tiles:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            gx2, gy2 = t.gx + dx, t.gy + dy
            if gx2 < 0 or gx2 >= nx or gy2 < 0 or gy2 >= ny:
                continue
            j = by_grid[(gx2, gy2)]
            ov = overlap_slices(t, tiles[j], P)
            if ov is None:
                continue
            si, sj = ov
            h1[(t.idx, j)] = fit_affine(preds[t.idx][si], preds[j][sj])
    return h1


# =============================================================================
# Correlation + misc diagnostics
# =============================================================================

def pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.size < 2 or y.size < 2:
        return float("nan")
    sx = float(np.std(x)); sy = float(np.std(y))
    if sx < 1e-15 or sy < 1e-15:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((a - b) ** 2)))


def correction_divergence(c_topo: np.ndarray, c_avg: np.ndarray) -> float:
    num = float(np.linalg.norm((c_topo - c_avg).ravel()))
    den = max(float(np.linalg.norm(c_topo.ravel())), float(np.linalg.norm(c_avg.ravel())), 1e-18)
    return num / den


def low_freq_energy_ratio_2d(x: np.ndarray, frac: float) -> float:
    x = np.asarray(x, dtype=float)
    Hx, Wx = x.shape
    F = np.fft.fftshift(np.fft.fft2(x))
    E = np.abs(F) ** 2
    cy, cx = Hx // 2, Wx // 2
    yy, xx = np.ogrid[:Hx, :Wx]
    ratio = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    r0 = frac * (min(Hx, Wx) / 2.0)
    low = E[ratio <= r0].sum()
    tot = E.sum()
    return float(low / tot) if tot > 0 else 0.0


def h1_slope_stats(h1: dict[tuple[int, int], Affine]) -> dict[str, float]:
    if not h1:
        return {"count": 0.0}
    a_vals = np.array([m.a for m in h1.values()], dtype=float)
    abs_a = np.abs(a_vals)
    return {
        "count": float(a_vals.size),
        "a_min": float(a_vals.min()),
        "a_med": float(np.median(a_vals)),
        "a_max": float(a_vals.max()),
        "frac_abs_a_gt_1_2": float(np.mean(abs_a > 1.2)),
        "frac_abs_a_gt_1_5": float(np.mean(abs_a > 1.5)),
    }


def tree_depth_stats(depth: Optional[list[int]]) -> dict[str, float]:
    if depth is None:
        return {"depth_count": 0.0}
    d_v = np.array([x for x in depth if x >= 0], dtype=float)
    if d_v.size == 0:
        return {"depth_count": 0.0}
    return {
        "depth_count": float(d_v.size),
        "depth_max": float(d_v.max()),
        "depth_med": float(np.median(d_v)),
        "depth_mean": float(d_v.mean()),
    }


def composed_root_slope_stats(M_to_root: Optional[list[Affine]]) -> dict[str, float]:
    if M_to_root is None:
        return {"root_count": 0.0}
    a_v = np.array([m.a for m in M_to_root], dtype=float)
    abs_a = np.abs(a_v)
    return {
        "root_count": float(a_v.size),
        "abs_a_root_med": float(np.median(abs_a)),
        "abs_a_root_max": float(abs_a.max()),
    }


# =============================================================================
# Drift scenarios
# =============================================================================

def make_clean_image(H: int, W: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, H, endpoint=False)
    x = np.linspace(0, 1, W, endpoint=False)
    Y, X = np.meshgrid(y, x, indexing="ij")
    clean = (
        np.sin(2 * np.pi * 2 * X)
        + 0.6 * np.sin(2 * np.pi * 3 * Y)
        + 0.2 * np.sign(np.sin(2 * np.pi * 1 * X))
    )
    noise = rng.normal(size=(H, W))
    clean += 0.15 * (noise - np.roll(noise, 1, axis=0))
    return clean.astype(float)


def apply_field_drift(img: np.ndarray) -> np.ndarray:
    H_img, W_img = img.shape
    y = np.linspace(-1, 1, H_img)
    x = np.linspace(-1, 1, W_img)
    Y, X = np.meshgrid(y, x, indexing="ij")
    gain = 1.0 + 0.25 * (0.5 * X + 0.5 * Y)
    bias = 0.10 * (X - Y)
    return gain * img + bias


def make_chart_drift_patches(
    clean: np.ndarray,
    tiles: list[Tile],
    P: int,
    *,
    sigma_a: float,
    sigma_b: float,
    seed: int,
    root_idx: int,
) -> tuple[list[np.ndarray], list[tuple[float, float]]]:
    """
    Per-tile drifted patches (no mosaic overwrite, no contamination).
    """
    rng = np.random.default_rng(seed)
    patches: list[np.ndarray] = []
    params: list[tuple[float, float]] = []

    for t in tiles:
        patch = clean[t.y0:t.y0 + P, t.x0:t.x0 + P].copy()
        if t.idx == root_idx:
            a, b_val = 1.0, 0.0
        else:
            a = float(rng.normal(1.0, sigma_a))
            b_val = float(rng.normal(0.0, sigma_b))
        patches.append(a * patch + b_val)
        params.append((a, b_val))

    return patches, params


# =============================================================================
# Transport/gauge utilities
# =============================================================================

def bfs_tree_from_root(
    tiles: list[Tile],
    grid: tuple[int, int],
    h1: dict[tuple[int, int], Affine],
    root: int,
) -> tuple[list[Affine], list[int]]:
    """
    BFS spanning tree; returns:
      M[i]: affine mapping tile i -> root
      depth[i]
    Uses edges (child -> parent).
    """
    nx, ny = grid
    by_grid = {(t.gx, t.gy): t.idx for t in tiles}

    M = [Affine(1.0, 0.0) for _ in tiles]
    depth = [-1 for _ in tiles]

    q: deque[int] = deque([root])
    depth[root] = 0
    M[root] = Affine(1.0, 0.0)

    while q:
        cur = q.popleft()
        gx, gy = tiles[cur].gx, tiles[cur].gy
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            gx2, gy2 = gx + dx, gy + dy
            if not (0 <= gx2 < nx and 0 <= gy2 < ny):
                continue
            nb = by_grid[(gx2, gy2)]
            if depth[nb] != -1:
                continue
            edge = h1.get((nb, cur))  # nb -> cur
            if edge is None:
                continue
            depth[nb] = depth[cur] + 1
            M[nb] = M[cur].compose(edge)
            q.append(nb)

    return M, depth


def map_patch_to_base(
    patch: np.ndarray,
    *,
    src_idx: int,
    base_idx: int,
    tiles: list[Tile],
    grid: tuple[int, int],
    h1: dict[tuple[int, int], Affine],
    transport: Transport,
    M_to_root: Optional[list[Affine]],
) -> np.ndarray:
    if src_idx == base_idx:
        return patch

    if transport == "tree":
        assert M_to_root is not None
        g = M_to_root[base_idx].inv().compose(M_to_root[src_idx])
        return g(patch)

    # local (Manhattan x-then-y) path; may be long if base_idx is root and src far away
    nx, ny = grid
    by_grid = {(t.gx, t.gy): t.idx for t in tiles}
    cur = src_idx
    gtot = Affine(1.0, 0.0)

    gbx, gby = tiles[base_idx].gx, tiles[base_idx].gy

    while tiles[cur].gx != gbx:
        step = -1 if tiles[cur].gx > gbx else 1
        nxt_g = (tiles[cur].gx + step, tiles[cur].gy)
        if not (0 <= nxt_g[0] < nx):
            break
        nxt = by_grid[nxt_g]
        edge = h1.get((cur, nxt))
        if edge is None:
            break
        gtot = edge.compose(gtot)
        cur = nxt

    while tiles[cur].gy != gby:
        step = -1 if tiles[cur].gy > gby else 1
        nxt_g = (tiles[cur].gx, tiles[cur].gy + step)
        if not (0 <= nxt_g[1] < ny):
            break
        nxt = by_grid[nxt_g]
        edge = h1.get((cur, nxt))
        if edge is None:
            break
        gtot = edge.compose(gtot)
        cur = nxt

    return gtot(patch)


# =============================================================================
# Covering tiles (generalized radius)
# =============================================================================

def owner_tile_idx_for_cell(
    x0: int, y0: int,
    *,
    H_img: int, W_img: int,
    P: int, S: int,
    grid_img: tuple[int, int],
    by_grid: dict[tuple[int, int], int],
) -> int:
    nx, ny = grid_img
    bx = min(x0, W_img - P)
    by = min(y0, H_img - P)
    gx = min(bx // S, nx - 1)
    gy = min(by // S, ny - 1)
    return by_grid[(gx, gy)]


def covering_tiles_for_cell(
    x0: int, y0: int,
    *,
    H_img: int, W_img: int,
    P: int, S: int,
    grid_img: tuple[int, int],
    by_grid: dict[tuple[int, int], int],
) -> list[int]:
    """
    Tiles whose support can overlap the stride cell [x0,x0+S)×[y0,y0+S).

    If tile starts are on the stride grid, a tile that covers x0 must start at
    x0 - k*S for k in [0, ceil(P/S)-1]. Same for y0.
    """
    nx, ny = grid_img
    base_idx = owner_tile_idx_for_cell(x0, y0, H_img=H_img, W_img=W_img, P=P, S=S, grid_img=grid_img, by_grid=by_grid)
    gx = tiles_by_idx[base_idx][0]
    gy = tiles_by_idx[base_idx][1]

    radius = (P + S - 1) // S  # ceil(P/S)
    cand = []
    for ddy in range(0, -radius, -1):
        for ddx in range(0, -radius, -1):
            gx2, gy2 = gx + ddx, gy + ddy
            if 0 <= gx2 < nx and 0 <= gy2 < ny:
                cand.append(by_grid[(gx2, gy2)])
    # unique
    return sorted(set(cand))


# =============================================================================
# Decode BASE / AVG / TOPO
# =============================================================================

def decode_predictions(
    target_shape: tuple[int, int],
    tiles: list[Tile],
    grid_img: tuple[int, int],
    P: int,
    S: int,
    preds: list[np.ndarray],
    h1: dict[tuple[int, int], Affine],
    *,
    base_strategy: BaseStrategy,
    weighting: Weighting,
    transport: Transport,
    root_idx: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[list[Affine]], Optional[list[int]]]:
    """
    Returns:
      pred_base, pred_avg, pred_topo, corr_avg, corr_topo, M_to_root, depth
    """
    H_img, W_img = target_shape
    nx, ny = grid_img
    by_grid = {(t.gx, t.gy): t.idx for t in tiles}

    Wts = np.ones((P, P), dtype=float) if weighting == "uniform" else tent_weights(P)

    M_to_root = None
    depth = None
    if transport == "tree":
        M_to_root, depth = bfs_tree_from_root(tiles, grid_img, h1, root_idx)

    pred_base = np.zeros((H_img, W_img), dtype=float)
    pred_avg = np.zeros((H_img, W_img), dtype=float)
    pred_topo = np.zeros((H_img, W_img), dtype=float)

    for y0 in range(0, H_img, S):
        for x0 in range(0, W_img, S):
            ys, ye = y0, min(y0 + S, H_img)
            xs, xe = x0, min(x0 + S, W_img)
            sl_out = (slice(ys, ye), slice(xs, xe))

            owner_idx = owner_tile_idx_for_cell(x0, y0, H_img=H_img, W_img=W_img, P=P, S=S, grid_img=grid_img, by_grid=by_grid)

            if base_strategy == "root":
                base_idx = root_idx
            else:
                base_idx = owner_idx

            # pred_base patch:
            # - owner base: directly use owner tile prediction on this cell region
            # - root base: use owner tile prediction mapped into root gauge
            owner_t = tiles[owner_idx]
            sl_owner = (slice(ys - owner_t.y0, ye - owner_t.y0), slice(xs - owner_t.x0, xe - owner_t.x0))
            owner_patch = preds[owner_idx][sl_owner]

            if base_strategy == "root":
                base_patch = map_patch_to_base(
                    owner_patch,
                    src_idx=owner_idx,
                    base_idx=base_idx,
                    tiles=tiles,
                    grid=grid_img,
                    h1=h1,
                    transport=transport,
                    M_to_root=M_to_root,
                )
            else:
                base_patch = owner_patch

            pred_base[sl_out] = base_patch

            cov = covering_tiles_for_cell(
                x0, y0,
                H_img=H_img, W_img=W_img, P=P, S=S,
                grid_img=grid_img, by_grid=by_grid,
            )

            num_avg = np.zeros((ye - ys, xe - xs), dtype=float)
            num_topo = np.zeros_like(num_avg)
            den = np.zeros_like(num_avg)

            for tid in cov:
                t = tiles[tid]
                ov_y0 = max(ys, t.y0); ov_y1 = min(ye, t.y0 + P)
                ov_x0 = max(xs, t.x0); ov_x1 = min(xe, t.x0 + P)
                if ov_y0 >= ov_y1 or ov_x0 >= ov_x1:
                    continue

                slc = (slice(ov_y0 - ys, ov_y1 - ys), slice(ov_x0 - xs, ov_x1 - xs))
                slt = (slice(ov_y0 - t.y0, ov_y1 - t.y0), slice(ov_x0 - t.x0, ov_x1 - t.x0))

                patch = preds[tid][slt]
                w = Wts[slt]

                num_avg[slc] += patch * w
                den[slc] += w

                mapped = map_patch_to_base(
                    patch,
                    src_idx=tid,
                    base_idx=base_idx,
                    tiles=tiles,
                    grid=grid_img,
                    h1=h1,
                    transport=transport,
                    M_to_root=M_to_root,
                )
                num_topo[slc] += mapped * w

            pred_avg[sl_out] = num_avg / np.maximum(den, 1e-18)
            pred_topo[sl_out] = num_topo / np.maximum(den, 1e-18)

    corr_avg = pred_avg - pred_base
    corr_topo = pred_topo - pred_base
    return pred_base, pred_avg, pred_topo, corr_avg, corr_topo, M_to_root, depth


# =============================================================================
# H² holonomy + plateau
# =============================================================================

def h2_face_holonomy_mean(
    tiles: list[Tile],
    grid: tuple[int, int],
    P: int,
    preds: list[np.ndarray],
    h1: dict[tuple[int, int], Affine],
) -> float:
    nx, ny = grid
    by_grid = {(t.gx, t.gy): t.idx for t in tiles}

    rms_vals: list[float] = []
    for gy in range(ny - 1):
        for gx in range(nx - 1):
            A = by_grid[(gx, gy)]
            B = by_grid[(gx + 1, gy)]
            C = by_grid[(gx, gy + 1)]
            D = by_grid[(gx + 1, gy + 1)]

            gDB = h1.get((D, B)); gBA = h1.get((B, A))
            gDC = h1.get((D, C)); gCA = h1.get((C, A))
            if gDB is None or gBA is None or gDC is None or gCA is None:
                continue

            ov = overlap_slices(tiles[D], tiles[A], P)
            if ov is None:
                continue
            slD, _ = ov
            y = preds[D][slD]
            c = gBA(gDB(y)) - gCA(gDC(y))
            rms_vals.append(float(np.sqrt(np.mean(c**2))))

    return float(np.mean(rms_vals)) if rms_vals else 0.0


def beta_fit_loglog_censored(h0: list[float], h2: list[float], noise_floor: float) -> float:
    x_v = np.array(h0, dtype=float)
    y_v = np.array(h2, dtype=float)
    mask = (x_v > 0) & (y_v > noise_floor)
    if mask.sum() < 3:
        return float("nan")
    lx = np.log(x_v[mask])
    ly = np.log(y_v[mask])
    beta_val = np.polyfit(lx, ly, deg=1)[0]
    return float(beta_val)


# =============================================================================
# Global state needed by covering_tiles_for_cell (gx,gy by idx)
# =============================================================================

tiles_by_idx: dict[int, tuple[int, int]] = {}


# =============================================================================
# Main runner
# =============================================================================

def run() -> None:
    global tiles_by_idx
    tiles, grid_img, xs, ys = build_tiles(H, W, P, S)
    tiles_by_idx = {t.idx: (t.gx, t.gy) for t in tiles}

    N_px = H * W
    budgets_bits = [int(b * N_px) for b in BUDGETS_BPP]

    clean = make_clean_image(H, W, seed=0)

    print("2D protocol v7 (fixed)")
    print(f"  image={H}x{W} tile={P} stride={S} tiles={len(tiles)} grid={grid_img} basis={POLY_BASIS}")
    print(f"  degrees={DEGREES}")
    print(f"  budgets_bpp={BUDGETS_BPP}")
    print(f"  factors={len(DRIFTS)} drifts × {len(DEGREES)} degrees × {len(BASE_STRATEGIES)} base × {len(WEIGHTINGS)} w × {len(TRANSPORTS)} tr")
    print()

    for drift in DRIFTS:
        if drift == "none":
            target = clean
            fit_mode = "image"
            fit_payload = target
            drift_desc = "none"
        elif drift == "field":
            target = apply_field_drift(clean)
            fit_mode = "image"
            fit_payload = target
            drift_desc = "field_drift"
        else:
            # Positive control: target is CLEAN, but each tile is observed with its own drift.
            target = clean
            patches_fit, params = make_chart_drift_patches(
                clean, tiles, P,
                sigma_a=CHART_SIGMA_A, sigma_b=CHART_SIGMA_B,
                seed=CHART_SEED, root_idx=ROOT_TILE_IDX,
            )
            fit_mode = "patches"
            fit_payload = patches_fit
            drift_desc = f"chart_drift(sigma_a={CHART_SIGMA_A},sigma_b={CHART_SIGMA_B},root={ROOT_TILE_IDX})"

        print(f"=== drift={drift_desc} ===")

        plateau_h0: list[float] = []
        plateau_h2: list[float] = []

        for deg in DEGREES:
            if fit_mode == "image":
                preds, K = fit_h0_poly_tiles_from_image(fit_payload, tiles, P, deg, POLY_BASIS)  # type: ignore[arg-type]
            else:
                preds, K = fit_h0_poly_tiles_from_patches(fit_payload, P, deg, POLY_BASIS)  # type: ignore[arg-type]

            h1 = build_h1_all_adj(preds, tiles, grid_img, P)

            # overhead accounting
            nx, ny = grid_img
            undirected_edges = (nx - 1) * ny + nx * (ny - 1)
            h0_bits = len(tiles) * K * COEFF_BITS
            # conservative: store both directions independently => 4 scalars per undirected edge
            h1_bits_both = undirected_edges * 4 * AFFINE_BITS
            # optimistic: store one direction and derive inverse => 2 scalars per undirected edge
            h1_bits_inv = undirected_edges * 2 * AFFINE_BITS

            overhead_base = CONTAINER_BITS + h0_bits
            overhead_topo = CONTAINER_BITS + h0_bits + h1_bits_both

            # H0 proxy: mean per-tile RMSE vs target
            tile_rms = []
            for t in tiles:
                patch_t = target[t.y0:t.y0 + P, t.x0:t.x0 + P]
                tile_rms.append(float(np.sqrt(np.mean((preds[t.idx] - patch_t) ** 2))))
            h0_rmse_mean = float(np.mean(tile_rms))

            h2_mean = h2_face_holonomy_mean(tiles, grid_img, P, preds, h1)
            plateau_h0.append(h0_rmse_mean)
            plateau_h2.append(h2_mean)

            sstats = h1_slope_stats(h1)

            print(f"\n  deg={deg} K={K}")
            print(f"    overhead_bpp: base={overhead_base/N_px:.3f} topo(conservative)={ (overhead_base+h1_bits_both)/N_px :.3f} "
                  f"premium={h1_bits_both/N_px:.3f}  [alt inverse premium={h1_bits_inv/N_px:.3f}]")
            print(f"    H0_mean_tile_RMSE={h0_rmse_mean:.3e}  H2_face_holonomy_RMS={h2_mean:.3e}")
            print(f"    H1 slope stats: count={int(sstats.get('count',0))} "
                  f"a[min/med/max]=({sstats.get('a_min',0):+.3f},{sstats.get('a_med',0):+.3f},{sstats.get('a_max',0):+.3f}) "
                  f"frac|a|>1.2={sstats.get('frac_abs_a_gt_1_2',0):.3f} frac|a|>1.5={sstats.get('frac_abs_a_gt_1_5',0):.3f}")

            for base_strategy in BASE_STRATEGIES:
                for weighting in WEIGHTINGS:
                    for transport in TRANSPORTS:
                        pred_base, pred_avg, pred_topo, corr_avg, corr_topo, M_to_root, depth = decode_predictions(
                            (H, W),
                            tiles, grid_img,
                            P, S,
                            preds, h1,
                            base_strategy=base_strategy,
                            weighting=weighting,
                            transport=transport,
                            root_idx=ROOT_TILE_IDX,
                        )

                        # Prediction-only RMSE (instrument sanity)
                        rmse_base_pred = rmse(target, pred_base)
                        rmse_avg_pred = rmse(target, pred_avg)
                        rmse_topo_pred = rmse(target, pred_topo)

                        # Positive control warning: chart drift + root gauge should favor TOPO over AVG (prediction-only).
                        if drift == "chart" and base_strategy == POSCTRL_BASE and transport == POSCTRL_TR and weighting == POSCTRL_W:
                            if rmse_topo_pred >= rmse_avg_pred + POSCTRL_MARGIN:
                                print("    *** POSITIVE CONTROL WARNING ***")
                                print(f"    chart_drift under base={base_strategy}, tr={transport}, w={weighting}: "
                                      f"rmse_topo_pred={rmse_topo_pred:.3e} >= rmse_avg_pred={rmse_avg_pred:.3e}")
                                print("    This suggests H¹ transport/gauge may be ineffective or unstable in this configuration.")
                                print("    *******************************")

                        # Tree diagnostics
                        dstats = tree_depth_stats(depth)
                        rstats = composed_root_slope_stats(M_to_root)

                        # Correction diagnostics
                        delta_corr = correction_divergence(corr_topo, corr_avg)
                        diff = corr_topo - corr_avg
                        diff_lf = low_freq_energy_ratio_2d(diff, frac=LOW_FREQ_FRAC)
                        corr_corr_vs_rbase = pearson_corr(corr_topo, (target - pred_base))

                        # RD frontiers with refinement (single-stage)
                        front_avg = rd_frontier_budget_refined(
                            (target - pred_avg).ravel(),
                            overhead_bits=overhead_base,
                            budgets_bits=budgets_bits,
                            delta_bits=DELTA_BITS,
                            entropy_overhead_bits=ENTROPY_MODEL_OVERHEAD_BITS,
                            initial_n=INITIAL_N,
                            refine_rounds=REFINE_ROUNDS,
                            refine_pts_per_budget=REFINE_PTS_PER_BUDGET,
                        )
                        front_topo = rd_frontier_budget_refined(
                            (target - pred_topo).ravel(),
                            overhead_bits=overhead_topo,
                            budgets_bits=budgets_bits,
                            delta_bits=DELTA_BITS,
                            entropy_overhead_bits=ENTROPY_MODEL_OVERHEAD_BITS,
                            initial_n=INITIAL_N,
                            refine_rounds=REFINE_ROUNDS,
                            refine_pts_per_budget=REFINE_PTS_PER_BUDGET,
                        )

                        # Layered frontiers
                        front_layer_avg = rd_two_stage(
                            target=target,
                            pred_base=pred_base,
                            corr_true=corr_avg,
                            overhead_bits=overhead_base,
                            delta_bits=DELTA_BITS,
                            entropy_overhead_bits=ENTROPY_MODEL_OVERHEAD_BITS,
                            n_dc=LAYER_DC,
                            n_dr=LAYER_DR,
                        )
                        front_layer_topo = rd_two_stage(
                            target=target,
                            pred_base=pred_base,
                            corr_true=corr_topo,
                            overhead_bits=overhead_base,
                            delta_bits=DELTA_BITS,
                            entropy_overhead_bits=ENTROPY_MODEL_OVERHEAD_BITS,
                            n_dc=LAYER_DC,
                            n_dr=LAYER_DR,
                        )

                        # Budget comparisons
                        eps_abs = []
                        eps_rel = []
                        taus = []

                        for B in budgets_bits:
                            pa = best_at_budget(front_avg, B)
                            pt = best_at_budget(front_topo, B)
                            pla = best_at_budget(front_layer_avg, B)
                            plt = best_at_budget(front_layer_topo, B)

                            if pa is not None and pt is not None:
                                e = pt.rmse - pa.rmse
                                eps_abs.append(e)
                                eps_rel.append(e / max(pa.rmse, 1e-18))
                            if pla is not None and plt is not None:
                                taus.append(abs(pla.rmse - plt.rmse) / max(pla.rmse, plt.rmse, 1e-18))

                        eps_rel_med = float(np.median(eps_rel)) if eps_rel else float("nan")
                        eps_rel_min = float(np.min(eps_rel)) if eps_rel else float("nan")
                        eps_rel_max = float(np.max(eps_rel)) if eps_rel else float("nan")
                        tau_star = float(np.max(taus)) if taus else float("nan")

                        print(
                            "    "
                            f"cfg base={base_strategy:<5s} w={weighting:<7s} tr={transport:<5s} | "
                            f"predRMSE base/avg/topo={rmse_base_pred:.3e}/{rmse_avg_pred:.3e}/{rmse_topo_pred:.3e} | "
                            f"eps_rel[med,min,max]={eps_rel_med:+.3f},{eps_rel_min:+.3f},{eps_rel_max:+.3f} | "
                            f"tau*={tau_star:.2e} dcorr={delta_corr:.2e} diffLF={diff_lf:.2f} corr(c_topo,r_base)={corr_corr_vs_rbase:+.3f} | "
                            f"treeDepth[max,med]={dstats.get('depth_max',float('nan')):.0f},{dstats.get('depth_med',float('nan')):.1f} "
                            f"|a_root|max={rstats.get('abs_a_root_max',float('nan')):.2e}"
                        )

        # Plateau reporting
        rho = [h2_v / max(h0_v, 1e-18) for h0_v, h2_v in zip(plateau_h0, plateau_h2)]
        beta_v = beta_fit_loglog_censored(plateau_h0, plateau_h2, H2_NOISE_FLOOR_ABS)

        print("\n  Plateau readout (per degree):")
        for d, h0_v, h2_v, r in zip(DEGREES, plateau_h0, plateau_h2, rho):
            nf = " (noise-floor?)" if h2_v <= H2_NOISE_FLOOR_ABS else ""
            print(f"    deg={d:<2d} H0={h0_v:.3e} H2={h2_v:.3e} rho=H2/H0={r:.3e}{nf}")
        print(f"    log-log beta (censored, H2>{H2_NOISE_FLOOR_ABS:g}): beta={beta_v}")
        print()

    print("Done.")


if __name__ == "__main__":
    run()
