"""
hcc_v4_strict_rd_sweep.py  (budget-targeted refinement added)

Adds budget-targeted Δ refinement for single-stage RD curves (BASE/AVG/TOPO):

- Start with an initial log Δ grid.
- Evaluate RD points.
- For each target budget B, find the nearest point below B and nearest above B
  (in bits_total), then densify Δ samples in the log-interval between their Δs.
- Repeat for a few rounds, then build the Pareto frontier.

This improves budget comparisons by reducing “grid coarseness” error.

(2-stage layered coders are left on a dense fixed grid; refinement there is 2D and
significantly more expensive.)
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from bisect import bisect_left, insort
from typing import Dict, Iterator, List, Optional, Tuple, Literal

import numpy as np
import zlib


# ── 1) Signal generation ──────────────────────────────────────────────────


def make_signal_parametric(
    n: int = 4096,
    *,
    seed: int = 42,
    snr_db: float = 15.0,
    spectral_slope: float = -1.5,
) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = np.linspace(0.0, 1.0, n, endpoint=False)

    clean = np.sin(2 * np.pi * 2 * t) + 0.6 * np.sin(2 * np.pi * 5 * t)

    freqs = np.fft.rfftfreq(n, d=1 / n)
    amp = np.zeros_like(freqs)
    nz = freqs > 0
    amp[nz] = freqs[nz] ** (spectral_slope / 2.0)

    noise_fft = amp * (rng.normal(size=len(freqs)) + 1j * rng.normal(size=len(freqs)))
    noise = np.fft.irfft(noise_fft, n=n)

    signal_power = float(np.mean(clean**2))
    noise_power = float(np.mean(noise**2))
    target_noise_power = signal_power / (10 ** (snr_db / 10.0))
    noise *= np.sqrt(target_noise_power / max(noise_power, 1e-18))

    return t, clean + noise


# ── 2) Cover + H^0 local polynomials ──────────────────────────────────────


@dataclass(frozen=True)
class Window:
    i: int
    start: int
    end: int  # exclusive


Interval = Tuple[int, int]
TailMode = Literal["add", "shift"]


def intersect_intervals(a: Interval, b: Interval) -> Optional[Interval]:
    s = max(a[0], b[0])
    e = min(a[1], b[1])
    return (s, e) if s < e else None


def triple_intersect(a: Interval, b: Interval, c: Interval) -> Optional[Interval]:
    ab = intersect_intervals(a, b)
    if ab is None:
        return None
    return intersect_intervals(ab, c)


def build_cover(
    n: int,
    *,
    win_size: int,
    stride: int,
    ensure_full_coverage: bool = True,
    tail_mode: TailMode = "add",
) -> List[Window]:
    if not (0 < stride <= win_size):
        raise ValueError("Require 0 < stride <= win_size")

    out: List[Window] = []
    for start in range(0, n - win_size + 1, stride):
        out.append(Window(i=len(out), start=start, end=start + win_size))

    if ensure_full_coverage:
        if not out:
            out = [Window(i=0, start=max(0, n - win_size), end=n)]
        else:
            if out[-1].end < n:
                tail_start = n - win_size
                if tail_mode == "add":
                    if tail_start != out[-1].start:
                        out.append(Window(i=len(out), start=tail_start, end=n))
                elif tail_mode == "shift":
                    last = out[-1]
                    out[-1] = Window(i=last.i, start=tail_start, end=n)
                else:
                    raise ValueError(f"Unknown tail_mode: {tail_mode}")

    return out


def compute_cover_sets(windows: List[Window], n: int) -> List[Tuple[int, ...]]:
    """
    For each t, return sorted tuple of windows covering t.
    Maintains sorted active list incrementally.
    """
    starts: Dict[int, List[int]] = {}
    ends: Dict[int, List[int]] = {}
    for w in windows:
        starts.setdefault(w.start, []).append(w.i)
        ends.setdefault(w.end, []).append(w.i)

    active: List[int] = []
    cover: List[Tuple[int, ...]] = [tuple() for _ in range(n)]

    for t in range(n):
        for i in ends.get(t, []):
            pos = bisect_left(active, i)
            if pos < len(active) and active[pos] == i:
                active.pop(pos)

        for i in starts.get(t, []):
            insort(active, i)

        cover[t] = tuple(active)

    return cover


def _local_u(idx: np.ndarray, w: Window) -> np.ndarray:
    mid = 0.5 * (w.start + (w.end - 1))
    half = 0.5 * (w.end - w.start - 1)
    if half <= 0:
        return np.zeros_like(idx, dtype=float)
    return (idx - mid) / half


@dataclass(frozen=True)
class LocalPoly:
    window: Window
    degree: int
    poly: np.poly1d


def fit_local_polys(f: np.ndarray, windows: List[Window], *, degree: int) -> List[LocalPoly]:
    polys: List[LocalPoly] = []
    for w in windows:
        idx = np.arange(w.start, w.end)
        if idx.size < degree + 1:
            c = float(np.mean(f[idx])) if idx.size else 0.0
            polys.append(LocalPoly(window=w, degree=0, poly=np.poly1d([c])))
            continue
        u = _local_u(idx, w)
        coeff = np.polyfit(u, f[idx], deg=degree)
        polys.append(LocalPoly(window=w, degree=degree, poly=np.poly1d(coeff)))
    return polys


def precompute_poly_values(polys: List[LocalPoly]) -> List[np.ndarray]:
    out: List[np.ndarray] = []
    for p in polys:
        idx = np.arange(p.window.start, p.window.end)
        out.append(p.poly(_local_u(idx, p.window)))
    return out


def h0_window_rmse(f: np.ndarray, p: LocalPoly) -> float:
    idx = np.arange(p.window.start, p.window.end)
    if idx.size == 0:
        return 0.0
    pred = p.poly(_local_u(idx, p.window))
    return float(np.sqrt(np.mean((pred - f[idx]) ** 2)))


# ── 3) H^1 affine maps (chain) ────────────────────────────────────────────


@dataclass(frozen=True)
class AffineMap:
    a: float
    b: float
    rms_fit: float

    def __call__(self, y: np.ndarray) -> np.ndarray:
        return self.a * y + self.b

    def compose(self, other: "AffineMap") -> "AffineMap":
        return AffineMap(self.a * other.a, self.a * other.b + self.b, 0.0)


def fit_affine_x_to_y(
    x: np.ndarray,
    y: np.ndarray,
    *,
    ridge_abs: float = 1e-9,
    ridge_rel: float = 1e-4,
    cond_fallback: float = 1e8,
) -> AffineMap:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size == 0:
        return AffineMap(1.0, 0.0, 0.0)

    X = np.stack([x, np.ones_like(x)], axis=1)
    XtX = X.T @ X
    scale = float(np.trace(XtX) / 2.0)
    lam = ridge_abs + ridge_rel * max(scale, 1e-12)
    XtX_reg = XtX + lam * np.eye(2)

    cond = float(np.linalg.cond(XtX_reg))
    if not np.isfinite(cond) or cond > cond_fallback:
        b = float(np.mean(y - x))
        pred = x + b
        rms = float(np.sqrt(np.mean((pred - y) ** 2)))
        return AffineMap(1.0, b, rms)

    a, b = np.linalg.solve(XtX_reg, X.T @ y)
    pred = a * x + b
    rms = float(np.sqrt(np.mean((pred - y) ** 2)))
    return AffineMap(float(a), float(b), rms)


def build_h1_backward_edges(
    poly_vals: List[np.ndarray],
    windows: List[Window],
) -> Dict[Tuple[int, int], AffineMap]:
    h1: Dict[Tuple[int, int], AffineMap] = {}
    for j in range(1, len(windows)):
        w_prev = windows[j - 1]
        w_cur = windows[j]
        ov = intersect_intervals((w_prev.start, w_prev.end), (w_cur.start, w_cur.end))
        if ov is None:
            continue
        s, e = ov
        prev_off = np.arange(s - w_prev.start, e - w_prev.start)
        cur_off = np.arange(s - w_cur.start, e - w_cur.start)
        p_prev = poly_vals[j - 1][prev_off]
        p_cur = poly_vals[j][cur_off]
        h1[(j, j - 1)] = fit_affine_x_to_y(p_cur, p_prev)
    return h1


def precompute_down_maps(
    h1_edges: Dict[Tuple[int, int], AffineMap],
    n_charts: int,
) -> List[List[AffineMap]]:
    down: List[List[AffineMap]] = [
        [AffineMap(1.0, 0.0, 0.0) for _ in range(n_charts)] for _ in range(n_charts)
    ]
    for src in range(n_charts):
        composed = AffineMap(1.0, 0.0, 0.0)
        down[src][src] = composed
        for dst in range(src - 1, -1, -1):
            edge = h1_edges.get((dst + 1, dst))
            composed = edge.compose(composed) if edge is not None else AffineMap(1.0, 0.0, 0.0)
            down[src][dst] = composed
    return down


# ── 4) Predictors + correction signals ────────────────────────────────────


@dataclass(frozen=True)
class Predictors:
    pred_base: np.ndarray
    pred_avg: np.ndarray
    pred_topo: np.ndarray
    corr_topo: np.ndarray
    corr_avg: np.ndarray


def predict_all(
    *,
    f: np.ndarray,
    windows: List[Window],
    cover_sets: List[Tuple[int, ...]],
    poly_vals: List[np.ndarray],
    down_maps: List[List[AffineMap]],
) -> Predictors:
    n = f.size
    pred_base = np.zeros(n, dtype=float)
    pred_avg = np.zeros(n, dtype=float)
    pred_topo = np.zeros(n, dtype=float)

    for t in range(n):
        charts = cover_sets[t]
        if not charts:
            continue

        base = charts[0]
        w_base = windows[base]
        base_val = float(poly_vals[base][t - w_base.start])
        pred_base[t] = base_val

        raw_vals = []
        for c in charts:
            w = windows[c]
            raw_vals.append(float(poly_vals[c][t - w.start]))
        pred_avg[t] = float(np.mean(raw_vals))

        mapped_vals = [base_val]
        for c in charts[1:]:
            w = windows[c]
            y = float(poly_vals[c][t - w.start])
            g = down_maps[c][base]
            mapped_vals.append(float(g(np.array([y], dtype=float))[0]))

        pred_topo[t] = float(np.mean(mapped_vals))

    corr_topo = pred_topo - pred_base
    corr_avg = pred_avg - pred_base
    return Predictors(pred_base, pred_avg, pred_topo, corr_topo, corr_avg)


def pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 2 or y.size < 2:
        return float("nan")
    if float(np.std(x)) < 1e-15 or float(np.std(y)) < 1e-15:
        return float("nan")
    x = x - x.mean()
    y = y - y.mean()
    den = float(np.sqrt((x * x).sum() * (y * y).sum()))
    if den <= 1e-18:
        return float("nan")
    return float((x * y).sum() / den)


# ── 5) RD coding primitives + budget-targeted refinement ───────────────────


def quantize_step(x: np.ndarray, delta: float) -> Tuple[np.ndarray, np.ndarray]:
    if not np.isfinite(delta) or delta <= 0.0:
        raise ValueError(f"delta must be finite and > 0, got {delta}")
    q = np.rint(x / delta).astype(np.int64)
    xhat = q.astype(float) * delta
    return q, xhat


def shannon_entropy_int_symbols(q: np.ndarray) -> float:
    flat = np.asarray(q, dtype=np.int64).ravel()
    if flat.size == 0:
        return 0.0
    _, counts = np.unique(flat, return_counts=True)
    p = counts.astype(float) / float(flat.size)
    return float(-(p * np.log2(p)).sum())


def make_delta_sweep(x: np.ndarray, *, n: int = 80) -> np.ndarray:
    sigma = float(np.std(x))
    sigma = max(sigma, 1e-12)
    d_min = sigma / 512.0
    d_max = sigma * 8.0
    return d_min * (d_max / d_min) ** np.linspace(0.0, 1.0, n)


@dataclass(frozen=True)
class RDPoint:
    bits_total: int
    rmse: float
    delta: float
    entropy_bps: float


def eval_rd_point(
    x: np.ndarray,
    *,
    overhead_bits: int,
    delta: float,
    delta_overhead_bits: int,
    entropy_model_overhead_bits: int,
) -> RDPoint:
    q, xhat = quantize_step(x, delta)
    H = shannon_entropy_int_symbols(q)
    n = x.size
    bits = overhead_bits + delta_overhead_bits + int(np.ceil(H * n)) + entropy_model_overhead_bits
    rmse = float(np.sqrt(np.mean((x - xhat) ** 2)))
    return RDPoint(bits_total=bits, rmse=rmse, delta=float(delta), entropy_bps=float(H))


def pareto_frontier(points: List[RDPoint]) -> List[RDPoint]:
    if not points:
        return []
    pts = sorted(points, key=lambda p: (p.bits_total, p.rmse))

    frontier: List[RDPoint] = []
    best_rmse = float("inf")
    last_bits: Optional[int] = None

    for p in pts:
        if last_bits is not None and p.bits_total == last_bits:
            continue
        if p.rmse < best_rmse - 1e-15:
            frontier.append(p)
            best_rmse = p.rmse
            last_bits = p.bits_total
    return frontier


def best_at_budget(frontier: List[RDPoint], budget_bits: int) -> Optional[RDPoint]:
    best: Optional[RDPoint] = None
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
    budgets_bits: List[int],
    delta_overhead_bits: int = 32,
    entropy_model_overhead_bits: int = 0,
    initial_n: int = 80,
    refine_rounds: int = 2,
    refine_points_per_budget: int = 24,
) -> List[RDPoint]:
    """
    Budget-targeted refinement for single-stage RD curves:

    1) Evaluate an initial Δ grid.
    2) For each budget B, find the nearest point below and above B (by bits_total),
       and densify Δ samples in the log-interval between their Δs.
    3) Repeat for a few rounds.
    4) Return Pareto frontier over all evaluated points.

    This does not assume strict monotonicity of bits vs Δ; it uses the currently
    sampled points to choose refinement intervals.
    """
    x = np.asarray(x, dtype=float)
    deltas = set(float(d) for d in make_delta_sweep(x, n=initial_n) if np.isfinite(d) and d > 0.0)

    points: Dict[float, RDPoint] = {}

    def eval_all(new_deltas: List[float]) -> None:
        for d in new_deltas:
            if d in points:
                continue
            points[d] = eval_rd_point(
                x,
                overhead_bits=overhead_bits,
                delta=d,
                delta_overhead_bits=delta_overhead_bits,
                entropy_model_overhead_bits=entropy_model_overhead_bits,
            )

    eval_all(sorted(deltas))

    for _ in range(refine_rounds):
        pts = sorted(points.values(), key=lambda p: p.bits_total)

        new: List[float] = []
        for B in budgets_bits:
            below = None
            above = None

            # nearest below: max bits_total <= B
            lo = 0
            hi = len(pts) - 1
            # linear scan is fine (len(pts) ~ 80-200), but keep it simple
            for p in pts:
                if p.bits_total <= B:
                    below = p
                else:
                    above = p
                    break

            if below is None or above is None:
                continue

            d0 = below.delta
            d1 = above.delta
            if not (np.isfinite(d0) and np.isfinite(d1)) or d0 <= 0.0 or d1 <= 0.0:
                continue
            if d0 == d1:
                continue

            dlo = min(d0, d1)
            dhi = max(d0, d1)
            # logspace refinement between dlo and dhi
            grid = np.exp(np.linspace(np.log(dlo), np.log(dhi), refine_points_per_budget + 2))[1:-1]
            new.extend(float(g) for g in grid)

        # de-dup and evaluate
        new = [d for d in new if np.isfinite(d) and d > 0.0 and d not in points]
        if not new:
            break
        eval_all(sorted(new))

    return pareto_frontier(list(points.values()))


# ── 6) Two-stage layered coder (unchanged, 2D grid) ───────────────────────


def rd_curve_two_stage_base_corr_res(
    *,
    f: np.ndarray,
    pred_base: np.ndarray,
    corr_true: np.ndarray,
    overhead_bits: int,
    delta_overhead_bits: int = 32,
    entropy_model_overhead_bits: int = 0,
    n_deltas_corr: int = 40,
    n_deltas_res: int = 50,
) -> List[RDPoint]:
    n = f.size
    deltas_corr = make_delta_sweep(corr_true, n=n_deltas_corr)

    pts: List[RDPoint] = []
    for dc in deltas_corr:
        dc = float(dc)
        if not np.isfinite(dc) or dc <= 0.0:
            continue

        qc, corr_hat = quantize_step(corr_true, dc)
        Hc = shannon_entropy_int_symbols(qc)
        bits_corr = delta_overhead_bits + int(np.ceil(Hc * n)) + entropy_model_overhead_bits

        pred_stage1 = pred_base + corr_hat
        r = f - pred_stage1

        deltas_res = make_delta_sweep(r, n=n_deltas_res)
        for dr in deltas_res:
            dr = float(dr)
            if not np.isfinite(dr) or dr <= 0.0:
                continue
            qr, r_hat = quantize_step(r, dr)
            Hr = shannon_entropy_int_symbols(qr)
            bits_res = delta_overhead_bits + int(np.ceil(Hr * n)) + entropy_model_overhead_bits

            recon = pred_stage1 + r_hat
            rmse_total = float(np.sqrt(np.mean((recon - f) ** 2)))
            bits_total = overhead_bits + bits_corr + bits_res

            pts.append(RDPoint(bits_total=bits_total, rmse=rmse_total, delta=dr, entropy_bps=Hc + Hr))

    return pts


# ── 7) Baselines (context only) ───────────────────────────────────────────


def raw_8bit_baselines(
    f: np.ndarray,
    *,
    container_overhead_bits: int,
    scale_overhead_bits: int = 32,
    headroom: float = 1.05,
) -> Tuple[int, int]:
    n = f.size
    scale = headroom * float(np.max(np.abs(f)))
    levels = 256
    x = np.clip(f, -scale, scale)
    q = np.round((x + scale) * (levels - 1) / (2.0 * scale)).astype(np.uint8)

    counts = np.bincount(q.ravel(), minlength=256).astype(float)
    p = counts[counts > 0] / float(q.size)
    H = float(-(p * np.log2(p)).sum())
    bits_entropy = container_overhead_bits + scale_overhead_bits + int(np.ceil(H * n))
    bits_zlib = container_overhead_bits + scale_overhead_bits + len(zlib.compress(q.tobytes(), 9)) * 8
    return bits_entropy, bits_zlib


# ── 8) Main experiment ────────────────────────────────────────────────────


def run_degree_sweep_strict_rd() -> None:
    n_points = 4096
    win_size = 512
    stride = 160
    degrees = [1, 2, 3, 5, 8, 12]

    coeff_bits = 16
    affine_param_bits = 16
    container_overhead_bits = 128
    delta_overhead_bits = 32
    entropy_model_overhead_bits = 0

    budgets_bps = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    budgets_bits = [int(b * n_points) for b in budgets_bps]

    _, f = make_signal_parametric(n_points, seed=42, snr_db=15.0, spectral_slope=-1.5)

    windows = build_cover(
        n_points, win_size=win_size, stride=stride,
        ensure_full_coverage=True, tail_mode="add",
    )
    cover_sets = compute_cover_sets(windows, n_points)
    n_charts = len(windows)

    bits_raw_ent, bits_raw_zlib = raw_8bit_baselines(f, container_overhead_bits=container_overhead_bits)
    print("Baselines (raw 8-bit quantized signal, context only):")
    print(f"  raw entropy-only bits: {bits_raw_ent} ({bits_raw_ent/n_points:.3f} bps)")
    print(f"  raw zlib bits:         {bits_raw_zlib} ({bits_raw_zlib/n_points:.3f} bps)")
    print()
    print("Budgets (bps):", ", ".join(f"{b:.1f}" for b in budgets_bps))
    print()

    for deg in degrees:
        polys = fit_local_polys(f, windows, degree=deg)
        poly_vals = precompute_poly_values(polys)

        # overhead uses actual stored degrees
        coeff_count = int(sum(p.degree + 1 for p in polys))
        h0_bits = coeff_count * coeff_bits

        # build H1
        h1_edges = build_h1_backward_edges(poly_vals, windows)
        h1_bits = len(h1_edges) * 2 * affine_param_bits

        down_maps = precompute_down_maps(h1_edges, n_charts)

        preds = predict_all(
            f=f, windows=windows, cover_sets=cover_sets,
            poly_vals=poly_vals, down_maps=down_maps,
        )

        overhead_base = container_overhead_bits + h0_bits
        overhead_topo = container_overhead_bits + h0_bits + h1_bits

        # residuals
        r_base = f - preds.pred_base
        r_avg = f - preds.pred_avg
        r_topo = f - preds.pred_topo

        # diagnostics
        corr_topo_std = float(np.std(preds.corr_topo))
        corr_topo_rms = float(np.sqrt(np.mean(preds.corr_topo**2)))
        corr_corr_vs_rbase = pearson_corr(preds.corr_topo, r_base)

        print(f"deg={deg} charts={n_charts}")
        print(
            f"  overhead_bps: base={overhead_base/n_points:.3f} topo={overhead_topo/n_points:.3f} "
            f"topo_premium={(overhead_topo-overhead_base)/n_points:.3f}"
        )
        print(
            f"  corr_topo: std={corr_topo_std:.3e} rms={corr_topo_rms:.3e} "
            f"corr(corr_topo, r_base)={corr_corr_vs_rbase:+.3f}"
        )

        # ── Budget-targeted refined frontiers (single-stage)
        front_base = rd_frontier_budget_refined(
            r_base,
            overhead_bits=overhead_base,
            budgets_bits=budgets_bits,
            delta_overhead_bits=delta_overhead_bits,
            entropy_model_overhead_bits=entropy_model_overhead_bits,
            initial_n=80,
            refine_rounds=2,
            refine_points_per_budget=24,
        )
        front_avg = rd_frontier_budget_refined(
            r_avg,
            overhead_bits=overhead_base,
            budgets_bits=budgets_bits,
            delta_overhead_bits=delta_overhead_bits,
            entropy_model_overhead_bits=entropy_model_overhead_bits,
            initial_n=80,
            refine_rounds=2,
            refine_points_per_budget=24,
        )
        front_topo = rd_frontier_budget_refined(
            r_topo,
            overhead_bits=overhead_topo,
            budgets_bits=budgets_bits,
            delta_overhead_bits=delta_overhead_bits,
            entropy_model_overhead_bits=entropy_model_overhead_bits,
            initial_n=80,
            refine_rounds=2,
            refine_points_per_budget=24,
        )

        # ── Two-stage layered controls (fixed dense 2D grid)
        front_layer_topo = pareto_frontier(
            rd_curve_two_stage_base_corr_res(
                f=f,
                pred_base=preds.pred_base,
                corr_true=preds.corr_topo,
                overhead_bits=overhead_base,
                delta_overhead_bits=delta_overhead_bits,
                entropy_model_overhead_bits=entropy_model_overhead_bits,
                n_deltas_corr=40,
                n_deltas_res=50,
            )
        )
        front_layer_avg = pareto_frontier(
            rd_curve_two_stage_base_corr_res(
                f=f,
                pred_base=preds.pred_base,
                corr_true=preds.corr_avg,
                overhead_bits=overhead_base,
                delta_overhead_bits=delta_overhead_bits,
                entropy_model_overhead_bits=entropy_model_overhead_bits,
                n_deltas_corr=40,
                n_deltas_res=50,
            )
        )

        print("  RMSE at budgets (BASE / AVG / TOPO / LAYER_TOPO / LAYER_AVG):")
        for bps, B in zip(budgets_bps, budgets_bits):
            pb = best_at_budget(front_base, B)
            pa = best_at_budget(front_avg, B)
            pt = best_at_budget(front_topo, B)
            plt = best_at_budget(front_layer_topo, B)
            pla = best_at_budget(front_layer_avg, B)

            rb = pb.rmse if pb else float("inf")
            ra = pa.rmse if pa else float("inf")
            rt = pt.rmse if pt else float("inf")
            rlt = plt.rmse if plt else float("inf")
            rla = pla.rmse if pla else float("inf")

            print(f"    {bps:>3.1f} bps: {rb:.2e} / {ra:.2e} / {rt:.2e} / {rlt:.2e} / {rla:.2e}")
        print()


if __name__ == "__main__":
    run_degree_sweep_strict_rd()
