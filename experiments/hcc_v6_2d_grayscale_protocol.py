# hcc_v6_2d_grayscale_protocol.py
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Literal, Optional, Tuple

import numpy as np

# ---------------- RD utils ----------------

@dataclass(frozen=True)
class RDPoint:
    bits_total: int
    rmse: float
    delta: float

def quantize_step(x: np.ndarray, delta: float) -> tuple[np.ndarray, np.ndarray]:
    if not np.isfinite(delta) or delta <= 0:
        delta = 1e-6
    q = np.rint(x / delta).astype(np.int64)
    xhat = q.astype(float) * delta
    return q, xhat

def entropy_int(q: np.ndarray) -> float:
    flat = q.ravel()
    if flat.size == 0:
        return 0.0
    qmin = int(flat.min()); qmax = int(flat.max())
    rng = qmax - qmin + 1
    if rng <= 200_000:
        counts = np.bincount((flat - qmin).astype(np.int64), minlength=rng).astype(float)
        p = counts[counts > 0] / float(flat.size)
        return float(-(p * np.log2(p)).sum())
    _, counts = np.unique(flat, return_counts=True)
    p = counts.astype(float) / float(flat.size)
    return float(-(p * np.log2(p)).sum())

def pareto_frontier(points: List[RDPoint]) -> List[RDPoint]:
    pts = sorted(points, key=lambda p: (p.bits_total, p.rmse))
    out: List[RDPoint] = []
    best = float("inf")
    last_bits = None
    for p in pts:
        if last_bits is not None and p.bits_total == last_bits:
            continue
        if p.rmse < best - 1e-15:
            out.append(p)
            best = p.rmse
            last_bits = p.bits_total
    return out

def best_at_budget(frontier: List[RDPoint], budget_bits: int) -> Optional[RDPoint]:
    best = None
    for p in frontier:
        if p.bits_total <= budget_bits:
            best = p
        else:
            break
    return best

def make_delta_sweep(x: np.ndarray, n: int = 80) -> np.ndarray:
    sigma = float(np.std(x))
    sigma = max(sigma, 1e-12)
    dmin = sigma / 512.0
    dmax = sigma * 16.0
    return dmin * (dmax / dmin) ** np.linspace(0.0, 1.0, n)

def eval_rd_point(x: np.ndarray, overhead_bits: int, delta_bits: int, delta: float) -> RDPoint:
    q, xhat = quantize_step(x, delta)
    H = entropy_int(q)
    bits = overhead_bits + delta_bits + int(np.ceil(H * x.size))
    rmse = float(np.sqrt(np.mean((x - xhat) ** 2)))
    return RDPoint(bits_total=bits, rmse=rmse, delta=float(delta))

def rd_frontier_budget_refined(
    x: np.ndarray,
    overhead_bits: int,
    budgets_bits: List[int],
    *,
    delta_bits: int = 32,
    initial_n: int = 80,
    refine_rounds: int = 2,
    refine_pts_per_budget: int = 20,
) -> List[RDPoint]:
    x = np.asarray(x, dtype=float)
    deltas = {float(d) for d in make_delta_sweep(x, initial_n) if np.isfinite(d) and d > 0}
    pts: Dict[float, RDPoint] = {}

    def eval_many(ds: Iterable[float]) -> None:
        for d in ds:
            if d in pts:
                continue
            pts[d] = eval_rd_point(x, overhead_bits, delta_bits, d)

    eval_many(sorted(deltas))

    for _ in range(refine_rounds):
        sorted_pts = sorted(pts.values(), key=lambda p: p.bits_total)
        new_ds: List[float] = []

        for B in budgets_bits:
            below = None
            above = None
            for p in sorted_pts:
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
            new_ds.extend(float(g) for g in grid)

        new_ds = [d for d in new_ds if np.isfinite(d) and d > 0 and d not in pts]
        if not new_ds:
            break
        eval_many(new_ds)

    return pareto_frontier(list(pts.values()))

def rd_two_stage(
    target: np.ndarray,
    pred_base: np.ndarray,
    corr_true: np.ndarray,
    overhead_bits: int,
    budgets_bits: List[int],
    *,
    delta_bits: int = 32,
    n_dc: int = 30,
    n_dr: int = 40,
) -> List[RDPoint]:
    """
    Two-stage: encode corr then residual after decoded corr.
    Returns Pareto frontier.
    """
    target = target.ravel().astype(float)
    pred_base = pred_base.ravel().astype(float)
    corr_true = corr_true.ravel().astype(float)
    n = target.size

    pts: List[RDPoint] = []
    deltas_c = make_delta_sweep(corr_true, n_dc)
    for dc in deltas_c:
        if not np.isfinite(dc) or dc <= 0:
            continue
        qc, corr_hat = quantize_step(corr_true, float(dc))
        Hc = entropy_int(qc)
        bits_c = delta_bits + int(np.ceil(Hc * n))

        stage1 = pred_base + corr_hat
        r = target - stage1
        deltas_r = make_delta_sweep(r, n_dr)
        for dr in deltas_r:
            if not np.isfinite(dr) or dr <= 0:
                continue
            qr, r_hat = quantize_step(r, float(dr))
            Hr = entropy_int(qr)
            bits_r = delta_bits + int(np.ceil(Hr * n))
            recon = stage1 + r_hat
            rmse = float(np.sqrt(np.mean((recon - target) ** 2)))
            pts.append(RDPoint(bits_total=overhead_bits + bits_c + bits_r, rmse=rmse, delta=float(dr)))

    return pareto_frontier(pts)

# ---------------- cover + weights ----------------

BaseStrategy = Literal["owner", "root"]
Weighting = Literal["uniform", "tent"]
Drift = Literal["none", "field", "chart"]

@dataclass(frozen=True)
class Tile:
    idx: int
    gx: int
    gy: int
    x0: int
    y0: int

def build_tiles(H: int, W: int, P: int, S: int) -> tuple[List[Tile], tuple[int,int], List[int], List[int]]:
    xs = list(range(0, W - P + 1, S))
    ys = list(range(0, H - P + 1, S))
    if xs[-1] != W - P:
        xs.append(W - P)
    if ys[-1] != H - P:
        ys.append(H - P)
    nx, ny = len(xs), len(ys)
    tiles: List[Tile] = []
    idx = 0
    for gy, y0 in enumerate(ys):
        for gx, x0 in enumerate(xs):
            tiles.append(Tile(idx=idx, gx=gx, gy=gy, x0=x0, y0=y0))
            idx += 1
    return tiles, (nx, ny), xs, ys

def tent_weights(P: int) -> np.ndarray:
    u = np.linspace(-1.0, 1.0, P) if P > 1 else np.array([0.0])
    w = 1.0 - np.abs(u)
    W = np.outer(w, w)
    return W

# ---------------- H0 poly (total degree) ----------------

def exps_2d_total(deg: int) -> List[tuple[int,int]]:
    exps = []
    for a in range(deg + 1):
        for b in range(deg + 1 - a):
            exps.append((a,b))
    return exps

def poly_basis(P: int, deg: int) -> tuple[np.ndarray, int]:
    u = np.linspace(-1.0, 1.0, P) if P > 1 else np.array([0.0])
    X, Y = np.meshgrid(u, u, indexing="xy")
    exps = exps_2d_total(deg)
    Phi = np.stack([(X**a) * (Y**b) for (a,b) in exps], axis=-1).reshape(P*P, -1)
    return Phi, Phi.shape[1]

def ridge_pinv(Phi: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    A = Phi.T @ Phi + ridge * np.eye(Phi.shape[1])
    return np.linalg.solve(A, Phi.T)

def fit_h0_tiles_poly(img: np.ndarray, tiles: List[Tile], P: int, deg: int, *, tile_obs: Optional[List[np.ndarray]]=None) -> tuple[List[np.ndarray], int]:
    Phi, K = poly_basis(P, deg)
    Pmat = ridge_pinv(Phi)
    preds: List[np.ndarray] = []
    for t in tiles:
        if tile_obs is None:
            patch = img[t.y0:t.y0+P, t.x0:t.x0+P]
        else:
            patch = tile_obs[t.idx]
        y = patch.reshape(-1)
        c = Pmat @ y
        yhat = (Phi @ c).reshape(P, P)
        preds.append(yhat)
    return preds, K

# ---------------- H1 affine maps between adjacent tiles ----------------

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

def fit_affine(x: np.ndarray, y: np.ndarray, ridge_rel: float = 1e-4, ridge_abs: float = 1e-9, cond_fallback: float = 1e8) -> Affine:
    x = x.reshape(-1).astype(float); y = y.reshape(-1).astype(float)
    X = np.stack([x, np.ones_like(x)], axis=1)
    XtX = X.T @ X
    lam = ridge_abs + ridge_rel * max(float(np.trace(XtX)/2.0), 1e-12)
    XtXr = XtX + lam * np.eye(2)
    cond = float(np.linalg.cond(XtXr))
    if not np.isfinite(cond) or cond > cond_fallback:
        b = float(np.mean(y - x))
        return Affine(1.0, b)
    a, b = np.linalg.solve(XtXr, X.T @ y)
    return Affine(float(a), float(b))

def tile_overlap_slices(a: Tile, b: Tile, P: int) -> Optional[tuple[tuple[slice,slice], tuple[slice,slice]]]:
    # overlap in global coords
    ax0, ay0 = a.x0, a.y0
    bx0, by0 = b.x0, b.y0
    s_x = max(ax0, bx0); e_x = min(ax0+P, bx0+P)
    s_y = max(ay0, by0); e_y = min(ay0+P, by0+P)
    if s_x >= e_x or s_y >= e_y:
        return None
    sa = (slice(s_y - ay0, e_y - ay0), slice(s_x - ax0, e_x - ax0))
    sb = (slice(s_y - by0, e_y - by0), slice(s_x - bx0, e_x - bx0))
    return sa, sb

def build_h1_adj(preds: List[np.ndarray], tiles: List[Tile], grid: tuple[int,int], P: int) -> Dict[tuple[int,int], Affine]:
    nx, ny = grid
    by_grid = {(t.gx, t.gy): t.idx for t in tiles}
    h1: Dict[tuple[int,int], Affine] = {}
    for t in tiles:
        for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
            gx2, gy2 = t.gx + dx, t.gy + dy
            if gx2 < 0 or gx2 >= nx or gy2 < 0 or gy2 >= ny:
                continue
            j = by_grid[(gx2, gy2)]
            ov = tile_overlap_slices(t, tiles[j], P)
            if ov is None:
                continue
            sa, sb = ov
            h1[(t.idx, j)] = fit_affine(preds[t.idx][sa], preds[j][sb])
    return h1

# ---------------- base selection + decoding ----------------

def decode_base_avg_topo(
    img_shape: tuple[int,int],
    tiles: List[Tile],
    grid: tuple[int,int],
    P: int,
    S: int,
    preds: List[np.ndarray],
    h1: Dict[tuple[int,int], Affine],
    *,
    base_strategy: BaseStrategy,
    weighting: Weighting,
    transport: Literal["local", "tree"],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns pred_base, pred_avg, pred_topo, corr_avg, corr_topo.

    transport="local": map contributors to base via up to 2 hops (x then y) within the 2x2 neighborhood
    transport="tree":  global root gauge M[t]->root, then g_{t->base}=inv(M[base])∘M[t]
    """
    H, W = img_shape
    nx, ny = grid
    by_grid = {(t.gx, t.gy): t.idx for t in tiles}

    # weights
    if weighting == "uniform":
        Wts = np.ones((P,P), dtype=float)
    else:
        Wts = tent_weights(P)

    # helper: list of covering tiles for an owner cell (x0,y0)
    def covering_tiles_for_cell(x0: int, y0: int) -> List[int]:
        # base tile is at (x0,y0) clamped to tail
        bx = min(x0, W - P)
        by = min(y0, H - P)
        gx = bx // S
        gy = by // S
        # but due to tail, mapping via grid coords is safer:
        # find nearest grid indices
        gx = min(gx, nx-1); gy = min(gy, ny-1)
        cand = []
        for ddy in (0, -1):
            for ddx in (0, -1):
                gx2, gy2 = gx + ddx, gy + ddy
                if 0 <= gx2 < nx and 0 <= gy2 < ny:
                    cand.append(by_grid[(gx2, gy2)])
        return cand

    # global tree transport
    M_to_root: Optional[List[Affine]] = None
    root_idx = 0

    if transport == "tree":
        # BFS spanning tree from root; store composed map tile->root
        M = [Affine(1.0, 0.0) for _ in range(len(tiles))]
        seen = [False]*len(tiles)
        q = [root_idx]
        seen[root_idx] = True
        while q:
            cur = q.pop(0)
            gxc, gyc = tiles[cur].gx, tiles[cur].gy
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                gx2, gy2 = gxc+dx, gyc+dy
                if not (0 <= gx2 < nx and 0 <= gy2 < ny):
                    continue
                nb = by_grid[(gx2, gy2)]
                if seen[nb]:
                    continue
                edge = h1.get((nb, cur))  # nb -> cur
                if edge is None:
                    continue
                M[nb] = M[cur].compose(edge)
                seen[nb] = True
                q.append(nb)
        M_to_root = M

    def map_tile_to_base(tile_idx: int, base_idx: int, patch: np.ndarray) -> np.ndarray:
        if tile_idx == base_idx:
            return patch
        if transport == "tree":
            assert M_to_root is not None
            g = M_to_root[base_idx].inv().compose(M_to_root[tile_idx])
            return g(patch)

        # local: only expect within a 2x2 neighborhood; use deterministic 1-2 hop composition:
        a = tile_idx
        b = base_idx
        ga, gb = tiles[a].gx, tiles[b].gx
        ha, hb = tiles[a].gy, tiles[b].gy

        cur = a
        gtot = Affine(1.0, 0.0)
        # move x toward base
        while tiles[cur].gx != gb:
            step = -1 if tiles[cur].gx > gb else 1
            nxt = by_grid[(tiles[cur].gx + step, tiles[cur].gy)]
            edge = h1.get((cur, nxt))
            if edge is None:
                break
            gtot = edge.compose(gtot)
            cur = nxt
        # move y toward base
        while tiles[cur].gy != hb:
            step = -1 if tiles[cur].gy > hb else 1
            nxt = by_grid[(tiles[cur].gx, tiles[cur].gy + step)]
            edge = h1.get((cur, nxt))
            if edge is None:
                break
            gtot = edge.compose(gtot)
            cur = nxt

        return gtot(patch)

    pred_base = np.zeros((H,W), dtype=float)
    pred_avg = np.zeros((H,W), dtype=float)
    pred_topo = np.zeros((H,W), dtype=float)

    # owner cells
    for y0 in range(0, H, S):
        for x0 in range(0, W, S):
            ys, ye = y0, min(y0+S, H)
            xs, xe = x0, min(x0+S, W)

            # choose base
            if base_strategy == "root":
                base_idx = root_idx
            else:
                # owner-cell base tile = tile with start (clamped)
                bx = min(x0, W-P); by = min(y0, H-P)
                gx = min(bx // S, nx-1)
                gy = min(by // S, ny-1)
                base_idx = by_grid[(gx,gy)]

            cov = covering_tiles_for_cell(x0, y0)

            # fill from tiles
            base_t = tiles[base_idx]
            sl_out = (slice(ys,ye), slice(xs,xe))
            
            # check if base_idx tile actually covers this cell
            in_y = (ys >= base_t.y0) and (ye <= base_t.y0 + P)
            in_x = (xs >= base_t.x0) and (xe <= base_t.x0 + P)
            
            if in_y and in_x:
                sl_base = (slice(ys - base_t.y0, ye - base_t.y0), slice(xs - base_t.x0, xe - base_t.x0))
                base_patch = preds[base_idx][sl_base]
            else:
                # fallback to owner tile for pred_base if the global base doesn't cover
                bx_own = min(x0, W - P); by_own = min(y0, H - P)
                gx_own = min(bx_own // S, nx - 1); gy_own = min(by_own // S, ny - 1)
                owner_idx = by_grid[(gx_own, gy_own)]
                ot = tiles[owner_idx]
                sl_own = (slice(ys - ot.y0, ye - ot.y0), slice(xs - ot.x0, xe - ot.x0))
                base_patch = preds[owner_idx][sl_own]
                
            pred_base[sl_out] = base_patch

            # AVG / TOPO accumulation
            num_avg = np.zeros((ye-ys, xe-xs), dtype=float)
            den = np.zeros_like(num_avg)
            num_topo = np.zeros_like(num_avg)

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

                mapped = map_tile_to_base(tid, base_idx, patch)
                num_topo[slc] += mapped * w

            pred_avg[sl_out] = num_avg / np.maximum(den, 1e-18)
            pred_topo[sl_out] = num_topo / np.maximum(den, 1e-18)

    corr_avg = pred_avg - pred_base
    corr_topo = pred_topo - pred_base
    return pred_base, pred_avg, pred_topo, corr_avg, corr_topo

# ---------------- H2 holonomy + plateau stats ----------------

def h2_face_holonomy(
    tiles: List[Tile],
    grid: tuple[int,int],
    P: int,
    preds: List[np.ndarray],
    h1: Dict[tuple[int,int], Affine],
) -> float:
    """
    Mean RMS holonomy on all 2x2 tile faces where 4-way overlap exists.
    c = (A<-B<-D)(p_D) - (A<-C<-D)(p_D) evaluated on A∩B∩C∩D region.
    """
    nx, ny = grid
    by_grid = {(t.gx, t.gy): t.idx for t in tiles}

    rms = []
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
            # 4-way overlap = intersection of A and D is enough for this grid structure
            tA = tiles[A]; tD = tiles[D]
            ov2 = tile_overlap_slices(tD, tA, P)
            if ov2 is None:
                continue
            slD = ov2[0]  # slice in D
            y = preds[D][slD]
            c = gBA(gDB(y)) - gCA(gDC(y))
            rms.append(float(np.sqrt(np.mean(c**2))))
    return float(np.mean(rms)) if rms else 0.0

def polyfit_loglog_beta(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float); y = np.asarray(y, float)
    mask = (x > 0) & (y > 0)
    if mask.sum() < 2:
        return float("nan")
    lx = np.log(x[mask]); ly = np.log(y[mask])
    b = np.polyfit(lx, ly, deg=1)[0]
    return float(b)

# ---------------- data generators ----------------

def make_base_image(H: int, W: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, H, endpoint=False)
    x = np.linspace(0, 1, W, endpoint=False)
    Y, X = np.meshgrid(y, x, indexing="ij")
    clean = (
        np.sin(2*np.pi*2*X) +
        0.6*np.sin(2*np.pi*3*Y) +
        0.2*np.sign(np.sin(2*np.pi*1*X))
    )
    noise = rng.normal(size=(H,W))
    clean += 0.15 * (noise - np.roll(noise, 1, axis=0))
    return clean.astype(float)

def apply_field_drift(img: np.ndarray) -> np.ndarray:
    H,W = img.shape
    y = np.linspace(-1, 1, H)
    x = np.linspace(-1, 1, W)
    Y,X = np.meshgrid(y,x,indexing="ij")
    gain = 1.0 + 0.25*(0.5*X + 0.5*Y)
    bias = 0.10*(X - Y)
    return gain*img + bias

def make_chart_drift_tiles(
    clean: np.ndarray,
    tiles: List[Tile],
    P: int,
    *,
    sigma_a: float,
    sigma_b: float,
    seed: int = 0,
    root_idx: int = 0,
) -> List[np.ndarray]:
    """
    Positive-control drift: each tile sees (a_i,b_i) applied to clean samples.
    Root tile is anchored at (1,0) to fix gauge.
    """
    rng = np.random.default_rng(seed)
    obs: List[np.ndarray] = []
    for t in tiles:
        patch = clean[t.y0:t.y0+P, t.x0:t.x0+P]
        if t.idx == root_idx:
            a, b = 1.0, 0.0
        else:
            a = float(rng.normal(1.0, sigma_a))
            b = float(rng.normal(0.0, sigma_b))
        obs.append(a*patch + b)
    return obs

# ---------------- experiment runner ----------------

def run_2d_protocol():
    H=W=256
    P=32
    S=16
    budgets_bpp = [0.25,0.5,0.75,1.0,1.5,2.0,3.0]
    degrees = [1,2,3,5]

    coeff_bits = 16
    affine_bits = 16
    container_bits = 128
    delta_bits = 32

    tiles, grid, xs, ys = build_tiles(H,W,P,S)
    N = H*W
    budgets_bits = [int(b*N) for b in budgets_bpp]

    # configurations (parity controls)
    base_strategies: List[BaseStrategy] = ["owner", "root"]
    weightings: List[Weighting] = ["uniform", "tent"]
    transports: List[Literal["local", "tree"]] = ["local", "tree"]
    drifts: List[Drift] = ["none", "field", "chart"]

    clean = make_base_image(H,W,seed=0)

    for drift in drifts:
        if drift == "none":
            target = clean
            tile_obs = None
            drift_desc = "none"
        elif drift == "field":
            target = apply_field_drift(clean)
            tile_obs = None
            drift_desc = "field_drift"
        else:
            # chart drift: target remains clean, but H0 is fit on per-tile drifted observations
            target = clean
            tile_obs = make_chart_drift_tiles(clean, tiles, P, sigma_a=0.10, sigma_b=0.05, seed=1, root_idx=0)
            drift_desc = "chart_drift(anchored root)"

        print(f"\n=== 2D drift={drift_desc} ===")

        # plateau arrays per degree (per config you could store; here we print for one reference config)
        plateau_h0 = []
        plateau_h2 = []

        for deg in degrees:
            preds, K = fit_h0_tiles_poly(target, tiles, P, deg, tile_obs=tile_obs)
            h1 = build_h1_adj(preds, tiles, grid, P)

            # overhead
            nx, ny = grid
            undirected_edges = (nx-1)*ny + nx*(ny-1)
            h0_bits = len(tiles) * K * coeff_bits
            h1_bits = undirected_edges * 4 * affine_bits
            overhead_base = container_bits + h0_bits
            overhead_topo = container_bits + h0_bits + h1_bits

            per_tile = []
            for t in tiles:
                patch_t = target[t.y0:t.y0+P, t.x0:t.x0+P]
                per_tile.append(float(np.sqrt(np.mean((preds[t.idx]-patch_t)**2))))
            h0_rmse_mean = float(np.mean(per_tile))

            h2_rms = h2_face_holonomy(tiles, grid, P, preds, h1)
            plateau_h0.append(h0_rmse_mean)
            plateau_h2.append(h2_rms)

            # run parity configs
            for base_strategy in base_strategies:
                for weighting in weightings:
                    for transport in transports:
                        pred_base, pred_avg, pred_topo, corr_avg, corr_topo = decode_base_avg_topo(
                            (H,W), tiles, grid, P, S, preds, h1,
                            base_strategy=base_strategy,
                            weighting=weighting,
                            transport=transport,
                        )

                        # single-stage RD (budget refined)
                        front_base = rd_frontier_budget_refined(
                            (target - pred_base).ravel(),
                            overhead_bits=overhead_base,
                            budgets_bits=budgets_bits,
                            delta_bits=delta_bits,
                        )
                        front_avg = rd_frontier_budget_refined(
                            (target - pred_avg).ravel(),
                            overhead_bits=overhead_base,
                            budgets_bits=budgets_bits,
                            delta_bits=delta_bits,
                        )
                        front_topo = rd_frontier_budget_refined(
                            (target - pred_topo).ravel(),
                            overhead_bits=overhead_topo,
                            budgets_bits=budgets_bits,
                            delta_bits=delta_bits,
                        )

                        # layered controls
                        front_layer_avg = rd_two_stage(
                            target, pred_base, corr_avg,
                            overhead_bits=overhead_base,
                            budgets_bits=budgets_bits,
                            delta_bits=delta_bits,
                        )
                        front_layer_topo = rd_two_stage(
                            target, pred_base, corr_topo,
                            overhead_bits=overhead_base,
                            budgets_bits=budgets_bits,
                            delta_bits=delta_bits,
                        )

                        # δ_corr and redundancy τ*
                        num = np.linalg.norm((corr_topo - corr_avg).ravel())
                        den = max(np.linalg.norm(corr_topo.ravel()), np.linalg.norm(corr_avg.ravel()), 1e-18)
                        delta_corr = float(num/den)

                        eps_abs = []
                        eps_rel = []
                        taus = []
                        for bpp, B in zip(budgets_bpp, budgets_bits):
                            pa = best_at_budget(front_avg, B)
                            pt = best_at_budget(front_topo, B)
                            pla = best_at_budget(front_layer_avg, B)
                            plt = best_at_budget(front_layer_topo, B)
                            if pa is None or pt is None or pla is None or plt is None:
                                continue
                            ea = pt.rmse - pa.rmse
                            eps_abs.append(ea)
                            eps_rel.append(ea / max(pa.rmse, 1e-18))
                            tau = abs(pla.rmse - plt.rmse) / max(pla.rmse, plt.rmse, 1e-18)
                            taus.append(tau)

                        tau_star = float(np.max(taus)) if taus else float("nan")
                        eps_rel_med = float(np.median(eps_rel)) if eps_rel else float("nan")

                        print(
                            f"deg={deg:<2d} base={base_strategy:<5s} w={weighting:<7s} tr={transport:<5s} | "
                            f"over_base={overhead_base/N:.3f} over_topo={overhead_topo/N:.3f} | "
                            f"H0={h0_rmse_mean:.3e} H2={h2_rms:.3e} | "
                            f"eps_rel_med={eps_rel_med:+.3f} tau*={tau_star:.3e} delta_corr={delta_corr:.3e}"
                        )

        h0a = np.array(plateau_h0)
        h2a = np.array(plateau_h2)
        beta = polyfit_loglog_beta(h0a, h2a)
        ratio = (h2a / np.maximum(h0a, 1e-18))
        print("\nPlateau test summary:")
        for d, h0v, h2v, rv in zip(degrees, h0a, h2a, ratio):
            print(f"  deg={d:<2d}  H0={h0v:.3e}  H2={h2v:.3e}  rho=H2/H0={rv:.3e}")
        print(f"  log-log beta (H2 ~ H0^beta): beta={beta:.3f}")

if __name__ == "__main__":
    run_2d_protocol()
