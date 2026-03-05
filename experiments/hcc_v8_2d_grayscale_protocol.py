"""
hcc_v8_2d_grayscale_protocol.py

A corrected and instrument-calibrated 2D grayscale HCC evaluation script.
Separates main RD comparison (owner mode) from gauge diagnostics (root mode).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional, Tuple

import numpy as np


# =============================================================================
# Config
# =============================================================================

Drift = Literal["none", "field", "chart"]
Weighting = Literal["uniform", "tent"]
Transport = Literal["local", "tree"]
BaseMode = Literal["owner", "root"]

H = W = 256
P = 32
S = 16

DEGREES = [1, 2, 3, 5]
BUDGETS_BPP = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]

DRIFTS: list[Drift] = ["none", "field", "chart"]
WEIGHTINGS: list[Weighting] = ["uniform", "tent"]
TRANSPORTS: list[Transport] = ["local", "tree"]
BASE_MODES: list[BaseMode] = ["owner", "root"]

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
) -> RDPoint:
    q, xhat = quantize_step(x, delta)
    H_val = entropy_int_symbols(q)
    bits = overhead_bits + DELTA_BITS + int(np.ceil(H_val * x.size)) + ENTROPY_MODEL_OVERHEAD_BITS
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
) -> list[RDPoint]:
    x = np.asarray(x, dtype=float)
    init = [float(d) for d in make_delta_sweep(x, INITIAL_N) if np.isfinite(d) and d > 0]
    pts_by_delta: dict[float, RDPoint] = {}

    def eval_many(deltas: Iterable[float]) -> None:
        for d in deltas:
            if d in pts_by_delta:
                continue
            pts_by_delta[d] = eval_rd_point(x, overhead_bits=overhead_bits, delta=d)

    eval_many(init)

    for _ in range(REFINE_ROUNDS):
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
            grid = np.exp(np.linspace(np.log(lo), np.log(hi), REFINE_PTS_PER_BUDGET + 2))[1:-1]
            new_deltas.extend(float(g) for g in grid)

        cand_ds = [d for d in new_deltas if np.isfinite(d) and d > 0 and d not in pts_by_delta]
        if not cand_ds:
            break
        eval_many(cand_ds)

    return pareto_frontier(list(pts_by_delta.values()))


def rd_two_stage(
    *,
    target: np.ndarray,
    pred_base: np.ndarray,
    corr_true: np.ndarray,
    overhead_bits: int,
) -> list[RDPoint]:
    t = target.reshape(-1).astype(float)
    b = pred_base.reshape(-1).astype(float)
    c = corr_true.reshape(-1).astype(float)
    n_p = t.size

    pts: list[RDPoint] = []
    deltas_c = make_delta_sweep(c, LAYER_DC)

    for dc in deltas_c:
        dc = float(dc)
        if not np.isfinite(dc) or dc <= 0:
            continue
        qc, c_hat = quantize_step(c, dc)
        Hc = entropy_int_symbols(qc)
        bits_c = DELTA_BITS + int(np.ceil(Hc * n_p)) + ENTROPY_MODEL_OVERHEAD_BITS

        stage1 = b + c_hat
        r = t - stage1
        deltas_r = make_delta_sweep(r, LAYER_DR)

        for dr in deltas_r:
            dr = float(dr)
            if not np.isfinite(dr) or dr <= 0:
                continue
            qr, r_hat = quantize_step(r, dr)
            Hr = entropy_int_symbols(qr)
            bits_r = DELTA_BITS + int(np.ceil(Hr * n_p)) + ENTROPY_MODEL_OVERHEAD_BITS

            recon = stage1 + r_hat
            rmse_val = float(np.sqrt(np.mean((recon - t) ** 2)))
            pts.append(RDPoint(bits_total=overhead_bits + bits_c + bits_r, rmse=rmse_val, delta=dr))

    return pareto_frontier(pts)


# =============================================================================
# Geometry: tiles + overlaps
# =============================================================================

@dataclass(frozen=True)
class Tile:
    idx: int
    gx: int
    gy: int
    x0: int
    y0: int


def build_tiles(H_in: int, W_in: int, P_in: int, S_in: int) -> tuple[list[Tile], tuple[int, int], list[int], list[int]]:
    xs = list(range(0, W_in - P_in + 1, S_in))
    ys = list(range(0, H_in - P_in + 1, S_in))
    if xs[-1] != W_in - P_in:
        xs.append(W_in - P_in)
    if ys[-1] != H_in - P_in:
        ys.append(H_in - P_in)
    nx, ny = len(xs), len(ys)

    tiles: list[Tile] = []
    idx = 0
    for gy, y0 in enumerate(ys):
        for gx, x0 in enumerate(xs):
            tiles.append(Tile(idx=idx, gx=gx, gy=gy, x0=x0, y0=y0))
            idx += 1
    return tiles, (nx, ny), xs, ys


def overlap_slices(a: Tile, b: Tile, P_in: int) -> Optional[tuple[tuple[slice, slice], tuple[slice, slice]]]:
    s_x = max(a.x0, b.x0); e_x = min(a.x0 + P_in, b.x0 + P_in)
    s_y = max(a.y0, b.y0); e_y = min(a.y0 + P_in, b.y0 + P_in)
    if s_x >= e_x or s_y >= e_y:
        return None
    sa = (slice(s_y - a.y0, e_y - a.y0), slice(s_x - a.x0, e_x - a.x0))
    sb = (slice(s_y - b.y0, e_y - b.y0), slice(s_x - b.x0, e_x - b.x0))
    return sa, sb


def tent_weights(P_in: int) -> np.ndarray:
    u = np.linspace(-1.0, 1.0, P_in) if P_in > 1 else np.array([0.0])
    w = 1.0 - np.abs(u)
    return np.outer(w, w).astype(float)


def owner_tile_idx_for_cell(x0: int, y0: int, *, H_in: int, W_in: int, P_in: int, S_in: int, grid_in: tuple[int,int], by_grid_in: dict[tuple[int,int],int]) -> int:
    nx, ny = grid_in
    bx = min(x0, W_in - P_in)
    by = min(y0, H_in - P_in)
    gx = min(bx // S_in, nx - 1)
    gy = min(by // S_in, ny - 1)
    return by_grid_in[(gx, gy)]


def covering_tiles_for_cell(x0: int, y0: int, *, H_in: int, W_in: int, P_in: int, S_in: int, grid_in: tuple[int,int], by_grid_in: dict[tuple[int,int],int]) -> list[int]:
    nx, ny = grid_in
    base_idx = owner_tile_idx_for_cell(x0, y0, H_in=H_in, W_in=W_in, P_in=P_in, S_in=S_in, grid_in=grid_in, by_grid_in=by_grid_in)
    base_g = None
    for (g, idx) in by_grid_in.items():
        if idx == base_idx:
            base_g = g
            break
    assert base_g is not None
    gx, gy = base_g

    radius = (P_in + S_in - 1) // S_in
    cand = []
    for ddy in range(0, -radius, -1):
        for ddx in range(0, -radius, -1):
            gx2, gy2 = gx + ddx, gy + ddy
            if 0 <= gx2 < nx and 0 <= gy2 < ny:
                cand.append(by_grid_in[(gx2, gy2)])
    return sorted(set(cand))


# =============================================================================
# H0 polynomial per tile
# =============================================================================

def exps_total(deg: int) -> list[tuple[int,int]]:
    exps = []
    for a in range(deg + 1):
        for b in range(deg + 1 - a):
            exps.append((a,b))
    return exps


def poly_basis(P_in: int, deg: int) -> tuple[np.ndarray, int]:
    u = np.linspace(-1.0, 1.0, P_in) if P_in > 1 else np.array([0.0])
    X, Y = np.meshgrid(u, u, indexing="xy")
    exps = exps_total(deg)
    Phi = np.stack([(X**a) * (Y**b) for (a,b) in exps], axis=-1).reshape(P_in*P_in, -1)
    return Phi, Phi.shape[1]


def ridge_pinv(Phi: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    A = Phi.T @ Phi + ridge * np.eye(Phi.shape[1])
    return np.linalg.solve(A, Phi.T)


def fit_h0_from_image(img: np.ndarray, tiles: list[Tile], P_in: int, deg: int) -> tuple[list[np.ndarray], int]:
    Phi, K = poly_basis(P_in, deg)
    Pmat = ridge_pinv(Phi)
    preds: list[np.ndarray] = []
    for t in tiles:
        patch = img[t.y0:t.y0+P_in, t.x0:t.x0+P_in]
        c = Pmat @ patch.reshape(-1)
        preds.append((Phi @ c).reshape(P_in,P_in))
    return preds, K


def fit_h0_from_patches(patches: list[np.ndarray], P_in: int, deg: int) -> tuple[list[np.ndarray], int]:
    Phi, K = poly_basis(P_in, deg)
    Pmat = ridge_pinv(Phi)
    preds: list[np.ndarray] = []
    for patch in patches:
        c = Pmat @ patch.reshape(-1)
        preds.append((Phi @ c).reshape(P_in,P_in))
    return preds, K


# =============================================================================
# H1 affine maps
# =============================================================================

@dataclass(frozen=True)
class Affine:
    a: float
    b: float
    def __call__(self, y_arr: np.ndarray) -> np.ndarray:
        return self.a * y_arr + self.b
    def compose(self, other: "Affine") -> "Affine":
        return Affine(self.a * other.a, self.a * other.b + self.b)
    def inv(self, eps: float = 1e-9) -> "Affine":
        if abs(self.a) < eps:
            return Affine(1.0, -self.b)
        ia = 1.0 / self.a
        return Affine(ia, -self.b * ia)


def fit_affine(x: np.ndarray, y: np.ndarray, ridge_rel: float = 1e-4, ridge_abs: float = 1e-9, cond_fallback: float = 1e8) -> Affine:
    x = x.reshape(-1).astype(float)
    y = y.reshape(-1).astype(float)
    if x.size == 0:
        return Affine(1.0, 0.0)
    X = np.stack([x, np.ones_like(x)], axis=1)
    XtX = X.T @ X
    lam = ridge_abs + ridge_rel * max(float(np.trace(XtX)/2.0), 1e-12)
    XtXr = XtX + lam * np.eye(2)
    cond = float(np.linalg.cond(XtXr))
    if not np.isfinite(cond) or cond > cond_fallback:
        b_val = float(np.mean(y - x))
        return Affine(1.0, b_val)
    a, b_val = np.linalg.solve(XtXr, X.T @ y)
    return Affine(float(a), float(b_val))


def build_h1_all_adj(preds: list[np.ndarray], tiles: list[Tile], grid_in: tuple[int,int], P_in: int) -> dict[tuple[int,int], Affine]:
    nx, ny = grid_in
    by_grid = {(t.gx,t.gy): t.idx for t in tiles}
    h1: dict[tuple[int,int], Affine] = {}
    for t in tiles:
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            gx2, gy2 = t.gx+dx, t.gy+dy
            if not (0 <= gx2 < nx and 0 <= gy2 < ny):
                continue
            j = by_grid[(gx2,gy2)]
            ov = overlap_slices(t, tiles[j], P_in)
            if ov is None:
                continue
            si, sj = ov
            h1[(t.idx, j)] = fit_affine(preds[t.idx][si], preds[j][sj])
    return h1


# =============================================================================
# Gauge/transport
# =============================================================================

def bfs_tree_to_root_maps(tiles: list[Tile], grid_in: tuple[int,int], h1: dict[tuple[int,int], Affine], root: int) -> tuple[list[Affine], list[int]]:
    nx, ny = grid_in
    by_grid = {(t.gx,t.gy): t.idx for t in tiles}
    M = [Affine(1.0, 0.0) for _ in tiles]
    depth = [-1 for _ in tiles]
    q: deque[int] = deque([root])
    depth[root] = 0
    M[root] = Affine(1.0, 0.0)
    while q:
        cur = q.popleft()
        gx, gy = tiles[cur].gx, tiles[cur].gy
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            gx2, gy2 = gx+dx, gy+dy
            if not (0 <= gx2 < nx and 0 <= gy2 < ny):
                continue
            nb = by_grid[(gx2,gy2)]
            if depth[nb] != -1:
                continue
            edge = h1.get((nb, cur))
            if edge is None:
                continue
            depth[nb] = depth[cur] + 1
            M[nb] = M[cur].compose(edge)
            q.append(nb)
    return M, depth


def map_patch(patch: np.ndarray, src: int, dst: int, *, tiles: list[Tile], grid_in: tuple[int,int], h1: dict[tuple[int,int], Affine], transport: Transport, M_to_root: Optional[list[Affine]]) -> np.ndarray:
    if src == dst:
        return patch
    if transport == "tree":
        assert M_to_root is not None
        g = M_to_root[dst].inv().compose(M_to_root[src])
        return g(patch)

    nx, ny = grid_in
    by_grid = {(t.gx,t.gy): t.idx for t in tiles}
    cur = src
    gtot = Affine(1.0, 0.0)
    gx_dst, gy_dst = tiles[dst].gx, tiles[dst].gy
    while tiles[cur].gx != gx_dst:
        step = -1 if tiles[cur].gx > gx_dst else 1
        nxt = by_grid[(tiles[cur].gx + step, tiles[cur].gy)]
        edge = h1.get((cur, nxt))
        if edge is None:
            break
        gtot = edge.compose(gtot)
        cur = nxt
    while tiles[cur].gy != gy_dst:
        step = -1 if tiles[cur].gy > gy_dst else 1
        nxt = by_grid[(tiles[cur].gx, tiles[cur].gy + step)]
        edge = h1.get((cur, nxt))
        if edge is None:
            break
        gtot = edge.compose(gtot)
        cur = nxt
    return gtot(patch)


# =============================================================================
# Decoders
# =============================================================================

@dataclass(frozen=True)
class OwnerDecode:
    pred_base: np.ndarray
    pred_avg: np.ndarray
    pred_topo: np.ndarray
    corr_avg: np.ndarray
    corr_topo: np.ndarray


def decode_owner_mode(
    target_shape: tuple[int,int],
    tiles: list[Tile],
    grid_in: tuple[int,int],
    preds: list[np.ndarray],
    h1: dict[tuple[int,int], Affine],
    *,
    weighting: Weighting,
    transport: Transport,
    root_idx: int,
) -> tuple[OwnerDecode, Optional[list[Affine]], Optional[list[int]]]:
    H_val, W_val = target_shape
    by_grid = {(t.gx,t.gy): t.idx for t in tiles}
    Wts = np.ones((P,P), float) if weighting == "uniform" else tent_weights(P)

    M_to_root = None
    depth = None
    if transport == "tree":
        M_to_root, depth = bfs_tree_to_root_maps(tiles, grid_in, h1, root_idx)

    pred_base = np.zeros((H_val,W_val), float)
    pred_avg = np.zeros((H_val,W_val), float)
    pred_topo = np.zeros((H_val,W_val), float)

    for y0 in range(0, H_val, S):
        for x0 in range(0, W_val, S):
            ys, ye = y0, min(y0+S, H_val)
            xs, xe = x0, min(x0+S, W_val)
            sl_out = (slice(ys,ye), slice(xs,xe))

            base_idx = owner_tile_idx_for_cell(x0,y0,H_in=H_val,W_in=W_val,P_in=P,S_in=S,grid_in=grid_in,by_grid_in=by_grid)
            base_t = tiles[base_idx]
            sl_base = (slice(ys-base_t.y0, ye-base_t.y0), slice(xs-base_t.x0, xe-base_t.x0))
            b_patch = preds[base_idx][sl_base]
            pred_base[sl_out] = b_patch

            cov = covering_tiles_for_cell(x0,y0,H_in=H_val,W_in=W_val,P_in=P,S_in=S,grid_in=grid_in,by_grid_in=by_grid)

            num_avg = np.zeros((ye-ys, xe-xs), float)
            num_topo = np.zeros_like(num_avg)
            den = np.zeros_like(num_avg)

            for tid in cov:
                t = tiles[tid]
                ov_y0 = max(ys, t.y0); ov_y1 = min(ye, t.y0+P)
                ov_x0 = max(xs, t.x0); ov_x1 = min(xe, t.x0+P)
                if ov_y0 >= ov_y1 or ov_x0 >= ov_x1:
                    continue
                slc = (slice(ov_y0-ys, ov_y1-ys), slice(ov_x0-xs, ov_x1-xs))
                slt = (slice(ov_y0-t.y0, ov_y1-t.y0), slice(ov_x0-t.x0, ov_x1-t.x0))
                patch = preds[tid][slt]
                w = Wts[slt]
                num_avg[slc] += patch * w
                den[slc] += w

                mapped = map_patch(patch, tid, base_idx, tiles=tiles, grid_in=grid_in, h1=h1, transport=transport, M_to_root=M_to_root)
                num_topo[slc] += mapped * w

            pred_avg[sl_out] = num_avg / np.maximum(den, 1e-18)
            pred_topo[sl_out] = num_topo / np.maximum(den, 1e-18)

    corr_avg = pred_avg - pred_base
    corr_topo = pred_topo - pred_base
    return OwnerDecode(pred_base, pred_avg, pred_topo, corr_avg, corr_topo), M_to_root, depth


def decode_root_topo_mode(
    target_shape: tuple[int,int],
    tiles: list[Tile],
    grid_in: tuple[int,int],
    preds: list[np.ndarray],
    h1: dict[tuple[int,int], Affine],
    *,
    weighting: Weighting,
    transport: Transport,
    root_idx: int,
) -> tuple[np.ndarray, Optional[list[Affine]], Optional[list[int]]]:
    H_val, W_val = target_shape
    by_grid = {(t.gx,t.gy): t.idx for t in tiles}
    Wts = np.ones((P,P), float) if weighting == "uniform" else tent_weights(P)

    M_to_root = None
    depth = None
    if transport == "tree":
        M_to_root, depth = bfs_tree_to_root_maps(tiles, grid_in, h1, root_idx)

    pred_topo_root = np.zeros((H_val,W_val), float)

    for y0 in range(0, H_val, S):
        for x0 in range(0, W_val, S):
            ys, ye = y0, min(y0+S, H_val)
            xs, xe = x0, min(x0+S, W_val)
            sl_out = (slice(ys,ye), slice(xs,xe))
            cov = covering_tiles_for_cell(x0,y0,H_in=H_val,W_in=W_val,P_in=P,S_in=S,grid_in=grid_in,by_grid_in=by_grid)
            num = np.zeros((ye-ys, xe-xs), float)
            den = np.zeros_like(num)
            for tid in cov:
                t = tiles[tid]
                ov_y0 = max(ys, t.y0); ov_y1 = min(ye, t.y0+P)
                ov_x0 = max(xs, t.x0); ov_x1 = min(xe, t.x0+P)
                if ov_y0 >= ov_y1 or ov_x0 >= ov_x1:
                    continue
                slc = (slice(ov_y0-ys, ov_y1-ys), slice(ov_x0-xs, ov_x1-xs))
                slt = (slice(ov_y0-t.y0, ov_y1-t.y0), slice(ov_x0-t.x0, ov_x1-t.x0))
                patch = preds[tid][slt]
                w = Wts[slt]
                mapped = map_patch(patch, tid, root_idx, tiles=tiles, grid_in=grid_in, h1=h1, transport=transport, M_to_root=M_to_root)
                num[slc] += mapped * w
                den[slc] += w
            pred_topo_root[sl_out] = num / np.maximum(den, 1e-18)
    return pred_topo_root, M_to_root, depth


# =============================================================================
# Diagnostics
# =============================================================================

def pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float).ravel()
    y = np.asarray(y, float).ravel()
    if x.size < 2 or y.size < 2:
        return float("nan")
    sx = float(np.std(x)); sy = float(np.std(y))
    if sx < 1e-15 or sy < 1e-15:
        return float("nan")
    return float(np.corrcoef(x,y)[0,1])


def low_freq_energy_ratio_2d(x: np.ndarray, frac: float) -> float:
    x = np.asarray(x, float)
    Hx, Wx = x.shape
    F = np.fft.fftshift(np.fft.fft2(x))
    E = np.abs(F)**2
    cy, cx = Hx//2, Wx//2
    yy_arr, xx_arr = np.ogrid[:Hx, :Wx]
    r_arr = np.sqrt((yy_arr-cy)**2 + (xx_arr-cx)**2)
    r0 = frac * (min(Hx,Wx)/2.0)
    low = E[r_arr <= r0].sum()
    tot = E.sum()
    return float(low/tot) if tot > 0 else 0.0


def h1_slope_stats(h1: dict[tuple[int,int], Affine]) -> dict[str,float]:
    if not h1:
        return {"count": 0.0}
    a_vals = np.array([m.a for m in h1.values()], float)
    abs_a = np.abs(a_vals)
    return {
        "count": float(a_vals.size),
        "a_min": float(a_vals.min()),
        "a_med": float(np.median(a_vals)),
        "a_max": float(a_vals.max()),
        "frac_abs_a_gt_1_2": float(np.mean(abs_a > 1.2)),
        "frac_abs_a_gt_1_5": float(np.mean(abs_a > 1.5)),
    }


def tree_depth_stats(depth: Optional[list[int]]) -> dict[str,float]:
    if depth is None:
        return {"depth_count": 0.0}
    d_vals = np.array([x for x in depth if x >= 0], float)
    if d_vals.size == 0:
        return {"depth_count": 0.0}
    return {
        "depth_count": float(d_vals.size),
        "depth_max": float(d_vals.max()),
        "depth_med": float(np.median(d_vals)),
        "depth_mean": float(d_vals.mean()),
    }


def composed_root_slope_stats(M_to_root: Optional[list[Affine]]) -> dict[str,float]:
    if M_to_root is None:
        return {"root_count": 0.0}
    a_vals = np.array([m.a for m in M_to_root], float)
    abs_a = np.abs(a_vals)
    return {
        "root_count": float(a_vals.size),
        "abs_a_root_med": float(np.median(abs_a)),
        "abs_a_root_max": float(abs_a.max()),
    }


def h2_face_holonomy_mean(tiles: list[Tile], grid_in: tuple[int,int], preds: list[np.ndarray], h1: dict[tuple[int,int], Affine]) -> float:
    nx, ny = grid_in
    by_grid = {(t.gx,t.gy): t.idx for t in tiles}
    rms_vals: list[float] = []
    for gy in range(ny-1):
        for gx in range(nx-1):
            A = by_grid[(gx,gy)]
            B = by_grid[(gx+1,gy)]
            C = by_grid[(gx,gy+1)]
            D = by_grid[(gx+1,gy+1)]
            gDB = h1.get((D,B)); gBA = h1.get((B,A))
            gDC = h1.get((D,C)); gCA = h1.get((C,A))
            if None in (gDB,gBA,gDC,gCA):
                continue
            ov = overlap_slices(tiles[D], tiles[A], P)
            if ov is None:
                continue
            slD, _ = ov
            y_patch = preds[D][slD]
            c_loop = gBA(gDB(y_patch)) - gCA(gDC(y_patch))
            rms_vals.append(float(np.sqrt(np.mean(c_loop**2))))
    return float(np.mean(rms_vals)) if rms_vals else 0.0


def beta_fit_loglog_censored(h0: list[float], h2: list[float], noise_floor: float) -> float:
    x_arr = np.array(h0, float)
    y_arr = np.array(h2, float)
    mask = (x_arr > 0) & (y_arr > noise_floor)
    if mask.sum() < 3:
        return float("nan")
    lx = np.log(x_arr[mask]); ly = np.log(y_arr[mask])
    return float(np.polyfit(lx, ly, deg=1)[0])


# =============================================================================
# Drift generators + chart drift oracle
# =============================================================================

def make_clean_image(H_in: int, W_in: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y_vals = np.linspace(0,1,H_in,endpoint=False)
    x_vals = np.linspace(0,1,W_in,endpoint=False)
    Y_arr, X_arr = np.meshgrid(y_vals,x_vals,indexing="ij")
    clean_arr = (
        np.sin(2*np.pi*2*X_arr) +
        0.6*np.sin(2*np.pi*3*Y_arr) +
        0.2*np.sign(np.sin(2*np.pi*1*X_arr))
    )
    noise_arr = rng.normal(size=(H_in,W_in))
    clean_arr += 0.15 * (noise_arr - np.roll(noise_arr,1,axis=0))
    return clean_arr.astype(float)


def apply_field_drift(img: np.ndarray) -> np.ndarray:
    H_val, W_val = img.shape
    y_vals = np.linspace(-1,1,H_val)
    x_vals = np.linspace(-1,1,W_val)
    Y_arr, X_arr = np.meshgrid(y_vals,x_vals,indexing="ij")
    gain_arr = 1.0 + 0.25*(0.5*X_arr + 0.5*Y_arr)
    bias_arr = 0.10*(X_arr - Y_arr)
    return gain_arr*img + bias_arr


def make_chart_drift_patches(clean_arr: np.ndarray, tiles: list[Tile]) -> tuple[list[np.ndarray], list[tuple[float,float]]]:
    rng = np.random.default_rng(CHART_SEED)
    patches: list[np.ndarray] = []
    params: list[tuple[float,float]] = []
    for t in tiles:
        patch = clean_arr[t.y0:t.y0+P, t.x0:t.x0+P].copy()
        if t.idx == ROOT_TILE_IDX:
            a_val, b_val = 1.0, 0.0
        else:
            a_val = float(rng.normal(1.0, CHART_SIGMA_A))
            b_val = float(rng.normal(0.0, CHART_SIGMA_B))
        patches.append(a_val*patch + b_val)
        params.append((a_val,b_val))
    return patches, params


def true_map_i_to_j(params: list[tuple[float,float]], i: int, j: int) -> Affine:
    ai, bi = params[i]
    aj, bj = params[j]
    a_val = aj / ai
    b_val = bj - a_val*bi
    return Affine(a_val, b_val)


def oracle_root_predictor(
    tiles: list[Tile],
    grid_in: tuple[int,int],
    preds_obs: list[np.ndarray],
    params: list[tuple[float,float]],
    *,
    weighting: Weighting,
) -> np.ndarray:
    H_val, W_val = H, W
    by_grid = {(t.gx,t.gy): t.idx for t in tiles}
    Wts = np.ones((P,P), float) if weighting == "uniform" else tent_weights(P)
    out_arr = np.zeros((H_val,W_val), float)
    for y0 in range(0, H_val, S):
        for x0 in range(0, W_val, S):
            ys, ye = y0, min(y0+S, H_val)
            xs, xe = x0, min(x0+S, W_val)
            sl_out = (slice(ys,ye), slice(xs,xe))
            cov = covering_tiles_for_cell(x0,y0,H_in=H_val,W_in=W_val,P_in=P,S_in=S,grid_in=grid_in,by_grid_in=by_grid)
            num_arr = np.zeros((ye-ys, xe-xs), float)
            den_arr = np.zeros_like(num_arr)
            for tid in cov:
                t = tiles[tid]
                ov_y0 = max(ys, t.y0); ov_y1 = min(ye, t.y0+P)
                ov_x0 = max(xs, t.x0); ov_x1 = min(xe, t.x0+P)
                if ov_y0 >= ov_y1 or ov_x0 >= ov_x1:
                    continue
                slc = (slice(ov_y0-ys, ov_y1-ys), slice(ov_x0-xs, ov_x1-xs))
                slt = (slice(ov_y0-t.y0, ov_y1-t.y0), slice(ov_x0-t.x0, ov_x1-t.x0))
                patch_obs = preds_obs[tid][slt]
                w_arr = Wts[slt]
                ai_val, bi_val = params[tid]
                inv_aff = Affine(1.0/ai_val, -bi_val/ai_val)
                patch_clean = inv_aff(patch_obs)
                num_arr[slc] += patch_clean * w_arr
                den_arr[slc] += w_arr
            out_arr[sl_out] = num_arr / np.maximum(den_arr, 1e-18)
    return out_arr


def chart_edge_fit_accuracy(
    tiles: list[Tile],
    grid_in: tuple[int,int],
    h1: dict[tuple[int,int], Affine],
    params: list[tuple[float,float]],
) -> dict[str,float]:
    if not h1:
        return {"edge_count": 0.0}
    a_err = []
    b_err = []
    a_rel = []
    for (i,j), g_aff in h1.items():
        gt_aff = true_map_i_to_j(params, i, j)
        a_err.append(abs(g_aff.a - gt_aff.a))
        b_err.append(abs(g_aff.b - gt_aff.b))
        a_rel.append(abs(g_aff.a - gt_aff.a) / max(abs(gt_aff.a), 1e-12))
    return {
        "edge_count": float(len(a_err)),
        "a_rel_med": float(np.median(a_rel)),
        "a_rel_max": float(np.max(a_rel)),
        "b_err_med": float(np.median(b_err)),
        "b_err_max": float(np.max(b_err)),
    }


# =============================================================================
# Main
# =============================================================================

def run() -> None:
    tiles, grid_in, xs_vals, ys_vals = build_tiles(H,W,P,S)
    nx, ny = grid_in
    N_px = H*W
    budgets_bits = [int(b_val*N_px) for b_val in BUDGETS_BPP]
    clean_arr = make_clean_image(H,W,seed=0)
    print("HCC v8 2D grayscale protocol")
    print(f"  image={H}x{W}, tile={P}, stride={S}, tiles={len(tiles)}, grid={grid_in}")
    print(f"  degrees={DEGREES}")
    print(f"  budgets_bpp={BUDGETS_BPP}")
    print(f"  factors: drifts={DRIFTS}, base_modes={BASE_MODES}, weights={WEIGHTINGS}, transports={TRANSPORTS}")
    print()
    for drift_type in DRIFTS:
        if drift_type == "none":
            target_arr = clean_arr
            fit_mode_val = "image"
            fit_payload_val = target_arr
            params_val = None
            drift_desc_val = "none"
        elif drift_type == "field":
            target_arr = apply_field_drift(clean_arr)
            fit_mode_val = "image"
            fit_payload_val = target_arr
            params_val = None
            drift_desc_val = "field_drift"
        else:
            target_arr = clean_arr
            patches_obs_val, params_val = make_chart_drift_patches(clean_arr, tiles)
            fit_mode_val = "patches"
            fit_payload_val = patches_obs_val
            drift_desc_val = f"chart_drift(sigma_a={CHART_SIGMA_A},sigma_b={CHART_SIGMA_B},root={ROOT_TILE_IDX})"
        print(f"=== drift={drift_desc_val} ===")
        plateau_h0_list = []
        plateau_h2_list = []
        for deg_val in DEGREES:
            if fit_mode_val == "image":
                preds_val, K_val = fit_h0_from_image(fit_payload_val, tiles, P, deg_val)  # type: ignore[arg-type]
            else:
                preds_val, K_val = fit_h0_from_patches(fit_payload_val, P, deg_val)  # type: ignore[arg-type]
            h1_val = build_h1_all_adj(preds_val, tiles, grid_in, P)
            undir_edges_val = (nx-1)*ny + nx*(ny-1)
            h0_bits_val = len(tiles) * K_val * COEFF_BITS
            h1_bits_both_val = undir_edges_val * 4 * AFFINE_BITS
            h1_bits_inv_val = undir_edges_val * 2 * AFFINE_BITS
            overhead_base_val = CONTAINER_BITS + h0_bits_val
            overhead_topo_cons_val = overhead_base_val + h1_bits_both_val
            tile_rms_list = []
            for t_tile in tiles:
                patch_t_tile = target_arr[t_tile.y0:t_tile.y0+P, t_tile.x0:t_tile.x0+P]
                tile_rms_list.append(float(np.sqrt(np.mean((preds_val[t_tile.idx] - patch_t_tile)**2))))
            h0_mean_val = float(np.mean(tile_rms_list))
            h2_mean_val = h2_face_holonomy_mean(tiles, grid_in, preds_val, h1_val)
            plateau_h0_list.append(h0_mean_val)
            plateau_h2_list.append(h2_mean_val)
            print(f"\n  deg={deg_val}  K={K_val}")
            print(f"    overhead_bpp base={overhead_base_val/N_px:.3f} topo_cons={overhead_topo_cons_val/N_px:.3f} "
                  f"premium_cons={h1_bits_both_val/N_px:.3f}  [inv_premium={h1_bits_inv_val/N_px:.3f}]")
            print(f"    H0_mean_tile_RMSE={h0_mean_val:.3e}  H2_face_holonomy_RMS={h2_mean_val:.3e}")
            if drift_type == "chart" and params_val is not None:
                acc_val = chart_edge_fit_accuracy(tiles, grid_in, h1_val, params_val)
                print(f"    chart-drift edge fit accuracy vs ground truth: "
                      f"a_rel_med={acc_val.get('a_rel_med',float('nan')):.3e} a_rel_max={acc_val.get('a_rel_max',float('nan')):.3e} "
                      f"b_err_med={acc_val.get('b_err_med',float('nan')):.3e} b_err_max={acc_val.get('b_err_max',float('nan')):.3e}")
            sstats_val = h1_slope_stats(h1_val)
            print(f"    H1 slopes: count={int(sstats_val.get('count',0))} a[min/med/max]=({sstats_val.get('a_min',0):+.3f},{sstats_val.get('a_med',0):+.3f},{sstats_val.get('a_max',0):+.3f}) "
                  f"frac|a|>1.2={sstats_val.get('frac_abs_a_gt_1_2',0):.3f} frac|a|>1.5={sstats_val.get('frac_abs_a_gt_1_5',0):.3f}")
            for b_mode_val in BASE_MODES:
                for w_val in WEIGHTINGS:
                    for tr_val in TRANSPORTS:
                        if b_mode_val == "owner":
                            dec_val, M_val, depth_val = decode_owner_mode(
                                (H,W), tiles, grid_in, preds_val, h1_val,
                                weighting=w_val, transport=tr_val, root_idx=ROOT_TILE_IDX
                            )
                            p_rmse_base_val = float(np.sqrt(np.mean((target_arr - dec_val.pred_base)**2)))
                            p_rmse_avg_val = float(np.sqrt(np.mean((target_arr - dec_val.pred_avg)**2)))
                            p_rmse_topo_val = float(np.sqrt(np.mean((target_arr - dec_val.pred_topo)**2)))
                            front_avg_val = rd_frontier_budget_refined(
                                (target_arr - dec_val.pred_avg).ravel(),
                                overhead_bits=overhead_base_val,
                                budgets_bits=budgets_bits,
                            )
                            front_topo_val = rd_frontier_budget_refined(
                                (target_arr - dec_val.pred_topo).ravel(),
                                overhead_bits=overhead_topo_cons_val,
                                budgets_bits=budgets_bits,
                            )
                            front_layer_avg_val = rd_two_stage(
                                target=target_arr, pred_base=dec_val.pred_base, corr_true=dec_val.corr_avg,
                                overhead_bits=overhead_base_val,
                            )
                            front_layer_topo_val = rd_two_stage(
                                target=target_arr, pred_base=dec_val.pred_base, corr_true=dec_val.corr_topo,
                                overhead_bits=overhead_base_val,
                            )
                            eps_rel_list = []
                            taus_list = []
                            for B_val in budgets_bits:
                                pa_val = best_at_budget(front_avg_val, B_val)
                                pt_val = best_at_budget(front_topo_val, B_val)
                                pla_val = best_at_budget(front_layer_avg_val, B_val)
                                plt_val = best_at_budget(front_layer_topo_val, B_val)
                                if pa_val is not None and pt_val is not None:
                                    eps_rel_list.append((pt_val.rmse - pa_val.rmse) / max(pa_val.rmse, 1e-18))
                                if pla_val is not None and plt_val is not None:
                                    taus_list.append(abs(pla_val.rmse - plt_val.rmse) / max(pla_val.rmse, plt_val.rmse, 1e-18))
                            e_med_val = float(np.median(eps_rel_list)) if eps_rel_list else float("nan")
                            t_star_val = float(np.max(taus_list)) if taus_list else float("nan")
                            d_corr_val = float(np.linalg.norm((dec_val.corr_topo - dec_val.corr_avg).ravel()) / max(np.linalg.norm(dec_val.corr_topo.ravel()), np.linalg.norm(dec_val.corr_avg.ravel()), 1e-18))
                            diffLF_val = low_freq_energy_ratio_2d(dec_val.corr_topo - dec_val.corr_avg, LOW_FREQ_FRAC)
                            c_c_rbase_val = pearson_corr(dec_val.corr_topo, (target_arr - dec_val.pred_base))
                            dst_val = tree_depth_stats(depth_val)
                            rst_val = composed_root_slope_stats(M_val)
                            print(
                                f"    cfg mode=owner w={w_val:<7s} tr={tr_val:<5s} | "
                                f"predRMSE base/avg/topo={p_rmse_base_val:.3e}/{p_rmse_avg_val:.3e}/{p_rmse_topo_val:.3e} | "
                                f"eps_rel_med={e_med_val:+.3f} tau*={t_star_val:.2e} dcorr={d_corr_val:.2e} diffLF={diffLF_val:.2f} corr(c_topo,r_base)={c_c_rbase_val:+.3f} | "
                                f"treeDepth[max,med]={dst_val.get('depth_max',float('nan')):.0f},{dst_val.get('depth_med',float('nan')):.1f} |a_root|max={rst_val.get('abs_a_root_max',float('nan')):.2e}"
                            )
                        else:
                            p_root_val, M_val, depth_val = decode_root_topo_mode(
                                (H,W), tiles, grid_in, preds_val, h1_val,
                                weighting=w_val, transport=tr_val, root_idx=ROOT_TILE_IDX
                            )
                            p_rmse_root_val = float(np.sqrt(np.mean((target_arr - p_root_val)**2)))
                            o_rmse_val = float("nan")
                            o_gap_val = float("nan")
                            if drift_type == "chart" and params_val is not None:
                                oracle_arr = oracle_root_predictor(tiles, grid_in, preds_val, params_val, weighting=w_val)
                                o_rmse_val = float(np.sqrt(np.mean((target_arr - oracle_arr)**2)))
                                o_gap_val = p_rmse_root_val - o_rmse_val
                            dst_val = tree_depth_stats(depth_val)
                            rst_val = composed_root_slope_stats(M_val)
                            print(
                                f"    cfg mode=root  w={w_val:<7s} tr={tr_val:<5s} | "
                                f"predRMSE topo_root={p_rmse_root_val:.3e} "
                                f"{'(oracle '+f'{o_rmse_val:.3e}, gap={o_gap_val:+.3e})' if drift_type=='chart' else ''} | "
                                f"treeDepth[max,med]={dst_val.get('depth_max',float('nan')):.0f},{dst_val.get('depth_med',float('nan')):.1f} |a_root|max={rst_val.get('abs_a_root_max',float('nan')):.2e}"
                            )
        rho_list = [h2_v/max(h0_v,1e-18) for h0_v,h2_v in zip(plateau_h0_list, plateau_h2_list)]
        beta_val = beta_fit_loglog_censored(plateau_h0_list, plateau_h2_list, H2_NOISE_FLOOR_ABS)
        print("\n  Plateau readout:")
        for d_v, h0_v, h2_v, r_v in zip(DEGREES, plateau_h0_list, plateau_h2_list, rho_list):
            nf_v = " (noise-floor?)" if h2_v <= H2_NOISE_FLOOR_ABS else ""
            print(f"    deg={d_v:<2d} H0={h0_v:.3e} H2={h2_v:.3e} rho=H2/H0={r_v:.3e}{nf_v}")
        print(f"    beta(log-log,censored H2>{H2_NOISE_FLOOR_ABS:g}) = {beta_val}")
        print()
    print("Done.")


if __name__ == "__main__":
    run()
