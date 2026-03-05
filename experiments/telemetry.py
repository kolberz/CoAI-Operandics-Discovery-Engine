"""
telemetry.py — H1/H2 diagnostic telemetry for HCC-style cover models.

Provides a small, stable telemetry packet suitable for “L2 monitoring”:

- H¹ edge fit errors on overlaps (value-space consistency)
- H¹ slope stability statistics (composition risk)
- H² face holonomy RMS (cycle inconsistency)
- ρ = H² / H⁰ normalization (robust plateau/coupling indicator)

This module is model-agnostic: you supply:
- per-chart predicted patches (preds[i] as ndarray of shape (P,P) for 2D),
- tile geometry (start positions),
- adjacency edges (i,j) for H¹ evaluation
- face loops (A,B,C,D) for H² holonomy evaluation

No RD coding here; this is telemetry only.

Dependencies: numpy
Python: 3.10+
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np


# =============================================================================
# Basic types
# =============================================================================

@dataclass(frozen=True, slots=True)
class Tile2D:
    """2D chart support: [y0,y0+P) × [x0,x0+P)."""
    idx: int
    x0: int
    y0: int
    P: int  # tile size


@dataclass(frozen=True, slots=True)
class Affine:
    """Value-space map g(y)=a*y+b"""
    a: float
    b: float

    def __call__(self, y: np.ndarray) -> np.ndarray:
        return self.a * y + self.b

    def compose(self, other: "Affine") -> "Affine":
        """(self ∘ other)(y)=self(other(y))"""
        return Affine(self.a * other.a, self.a * other.b + self.b)


@dataclass(frozen=True, slots=True)
class TelemetryPacket:
    # H0 quality proxy (you supply)
    h0_rmse_mean: float

    # H1 edge-fit metrics
    h1_edge_rmse_median: float
    h1_edge_rmse_p95: float
    h1_edge_rmse_max: float
    h1_edge_count: int

    # H1 slope stability metrics
    h1_abs_a_median: float
    h1_abs_a_p95: float
    h1_abs_a_max: float
    h1_frac_abs_a_gt_1_2: float
    h1_frac_abs_a_gt_1_5: float

    # H2 holonomy metrics
    h2_face_rms_mean: float
    h2_face_rms_p95: float
    h2_face_rms_max: float
    h2_face_count: int

    # Normalized holonomy
    rho: float

    # Optional: “top offenders” for debugging (indices into edges/faces arrays)
    worst_edges: tuple[int, ...]
    worst_faces: tuple[int, ...]


# =============================================================================
# Geometry helpers
# =============================================================================

def overlap_slices_2d(a: Tile2D, b: Tile2D) -> tuple[tuple[slice, slice], tuple[slice, slice]] | None:
    """
    Returns (slice_in_a, slice_in_b) for the overlap region, or None if no overlap.
    Slices are (y_slice, x_slice).
    """
    s_x = max(a.x0, b.x0)
    e_x = min(a.x0 + a.P, b.x0 + b.P)
    s_y = max(a.y0, b.y0)
    e_y = min(a.y0 + a.P, b.y0 + b.P)
    if s_x >= e_x or s_y >= e_y:
        return None

    sa = (slice(s_y - a.y0, e_y - a.y0), slice(s_x - a.x0, e_x - a.x0))
    sb = (slice(s_y - b.y0, e_y - b.y0), slice(s_x - b.x0, e_x - b.x0))
    return sa, sb


# =============================================================================
# Core telemetry computations
# =============================================================================

def edge_fit_rmse(
    preds: Sequence[np.ndarray],
    tiles: Sequence[Tile2D],
    h1: Mapping[tuple[int, int], Affine],
    edges: Sequence[tuple[int, int]],
) -> np.ndarray:
    """
    For each directed edge (i->j), compute overlap RMSE:
      sqrt(mean( (g_ij(p_i) - p_j)^2 )) on overlap.
    Returns array shape (len(edges),).
    """
    out = np.zeros(len(edges), dtype=float)
    for k, (i, j) in enumerate(edges):
        g = h1.get((i, j))
        if g is None:
            out[k] = np.nan
            continue
        ov = overlap_slices_2d(tiles[i], tiles[j])
        if ov is None:
            out[k] = np.nan
            continue
        si, sj = ov
        pi = preds[i][si]
        pj = preds[j][sj]
        diff = g(pi) - pj
        out[k] = float(np.sqrt(np.mean(diff * diff)))
    return out


def face_holonomy_rms(
    preds: Sequence[np.ndarray],
    tiles: Sequence[Tile2D],
    h1: Mapping[tuple[int, int], Affine],
    faces: Sequence[tuple[int, int, int, int]],
) -> np.ndarray:
    """
    For each face (A,B,C,D), compute square holonomy RMS on the A∩D overlap:

      c(y) = (A<-B<-D)(p_D) - (A<-C<-D)(p_D)

    where A<-B means using g_{B->A}, etc.

    Returns array shape (len(faces),).
    """
    out = np.zeros(len(faces), dtype=float)
    for k, (A, B, C, D) in enumerate(faces):
        gDB = h1.get((D, B))
        gBA = h1.get((B, A))
        gDC = h1.get((D, C))
        gCA = h1.get((C, A))
        if any(g is None for g in (gDB, gBA, gDC, gCA)):
            out[k] = np.nan
            continue

        ov = overlap_slices_2d(tiles[D], tiles[A])
        if ov is None:
            out[k] = np.nan
            continue
        sD, _ = ov
        y = preds[D][sD]
        c = gBA(gDB(y)) - gCA(gDC(y))
        out[k] = float(np.sqrt(np.mean(c * c)))
    return out


def summarize_nanaware(x: np.ndarray) -> tuple[float, float, float, int]:
    """Return (median, p95, max, count_valid)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan"), float("nan"), float("nan"), 0
    return float(np.median(x)), float(float(np.quantile(x, 0.95))), float(np.max(x)), int(x.size)


def topk_indices(x: np.ndarray, k: int) -> tuple[int, ...]:
    """Indices of top-k largest finite entries."""
    x = np.asarray(x, dtype=float)
    mask = np.isfinite(x)
    idx = np.nonzero(mask)[0]
    if idx.size == 0 or k <= 0:
        return ()
    vals = x[idx]
    k = min(k, idx.size)
    sel = np.argpartition(vals, -k)[-k:]
    top = idx[sel]
    # sort descending
    top = top[np.argsort(x[top])[::-1]]
    return tuple(int(i) for i in top)


def telemetry_packet_2d(
    *,
    preds: Sequence[np.ndarray],
    tiles: Sequence[Tile2D],
    h1: Mapping[tuple[int, int], Affine],
    edges: Sequence[tuple[int, int]],
    faces: Sequence[tuple[int, int, int, int]],
    # Provide an H0 proxy (mean per-tile RMSE against target, or residual std, etc.)
    h0_rmse_mean: float,
    worst_k: int = 5,
) -> TelemetryPacket:
    """
    Compute an L2 telemetry packet for a 2D cover.

    Notes:
    - This does NOT fit H1 maps; it evaluates an existing H1.
    - edges and faces should be the exact sets you care about monitoring.
    """
    # H1 edge fit errors
    e = edge_fit_rmse(preds, tiles, h1, edges)
    e_med, e_p95, e_max, e_n = summarize_nanaware(e)

    # H1 slope stats
    abs_a = np.array([abs(h1[(i, j)].a) for (i, j) in edges if (i, j) in h1], dtype=float)
    abs_a = abs_a[np.isfinite(abs_a)]
    if abs_a.size:
        a_med = float(np.median(abs_a))
        a_p95 = float(np.quantile(abs_a, 0.95))
        a_max = float(np.max(abs_a))
        frac_1_2 = float(np.mean(abs_a > 1.2))
        frac_1_5 = float(np.mean(abs_a > 1.5))
    else:
        a_med = a_p95 = a_max = frac_1_2 = frac_1_5 = float("nan")

    # H2 holonomy
    h2 = face_holonomy_rms(preds, tiles, h1, faces)
    h2_med, h2_p95, h2_max, h2_n = summarize_nanaware(h2)

    # rho normalization
    rho = (h2_med / max(h0_rmse_mean, 1e-18)) if np.isfinite(h2_med) else float("nan")

    return TelemetryPacket(
        h0_rmse_mean=float(h0_rmse_mean),

        h1_edge_rmse_median=e_med,
        h1_edge_rmse_p95=e_p95,
        h1_edge_rmse_max=e_max,
        h1_edge_count=e_n,

        h1_abs_a_median=a_med,
        h1_abs_a_p95=a_p95,
        h1_abs_a_max=a_max,
        h1_frac_abs_a_gt_1_2=frac_1_2,
        h1_frac_abs_a_gt_1_5=frac_1_5,

        h2_face_rms_mean=h2_med,
        h2_face_rms_p95=h2_p95,
        h2_face_rms_max=h2_max,
        h2_face_count=h2_n,

        rho=float(rho),

        worst_edges=topk_indices(e, worst_k),
        worst_faces=topk_indices(h2, worst_k),
    )
