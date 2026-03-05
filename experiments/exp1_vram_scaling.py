"""
Experiment 1: Activation Memory Scaling
========================================
Measures peak VRAM vs depth for:
  (A) Standard backprop  — stores all activations, O(L) memory
  (B) Gradient checkpoint — recomputes activations, O(1) memory

Expected: (A) steep linear slope, (B) shallow slope.
The SLOPE DIFFERENCE is the per-layer activation cost.
Both slopes are nonzero because weights + gradients still scale as O(L).

Usage:  python exp1_vram_scaling.py
Requires: PyTorch >= 2.0, CUDA GPU

Adjust HIDDEN, BATCH, SEQLEN if you OOM on your hardware.
"""

import torch
import torch.nn as nn
import torch.utils.checkpoint as cp
import time, gc, sys, os
try:
    import psutil
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
    import psutil

# ── Config (tune for your GPU) ────────────
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
HIDDEN = 256  # Reduced for CPU
BATCH  = 4    # Reduced for CPU
SEQLEN = 64   # Reduced for CPU
DEPTHS = [2, 4, 8, 16] # Reduced for CPU

if DEVICE == "cpu":
    print("Warning: Running on CPU. Results will be slow and not representative of VRAM scaling.")

def flush():
    gc.collect()

def peak_mib():
    # Return RSS in MiB
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 2**20


class Block(nn.Module):
    """Residual FFN block (simplified transformer layer, no attention)."""
    def __init__(self, d):
        super().__init__()
        self.ln   = nn.LayerNorm(d)
        self.up   = nn.Linear(d, 4*d, bias=False)   # expansion
        self.down = nn.Linear(4*d, d, bias=False)    # projection
    def forward(self, x):
        return x + self.down(nn.functional.gelu(self.up(self.ln(x))))


def run_trial(depth, use_checkpoint):
    """Build model, run one forward+backward, return (peak_MiB, seconds)."""
    flush()

    blocks = nn.ModuleList([Block(HIDDEN) for _ in range(depth)]).to(DEVICE)
    head   = nn.Linear(HIDDEN, 1, bias=False).to(DEVICE)
    x      = torch.randn(BATCH, SEQLEN, HIDDEN, device=DEVICE)

    # Warmup (compile kernels, stabilize allocator)
    for _ in range(3):
        h = x
        for b in blocks:
            h = cp.checkpoint(b, h, use_reentrant=False) if use_checkpoint else b(h)
        head(h).sum().backward()
        blocks.zero_grad(set_to_none=True); head.zero_grad(set_to_none=True)

    # Measured run
    flush()
    t0 = time.perf_counter()

    h = x
    for b in blocks:
        h = cp.checkpoint(b, h, use_reentrant=False) if use_checkpoint else b(h)
    head(h).sum().backward()

    elapsed = time.perf_counter() - t0
    mem = peak_mib()

    del blocks, head, x, h
    flush()
    return mem, elapsed


# ── Main ──────────────────────────────────
print(f"Device: {DEVICE}")
print(f"Config: hidden={HIDDEN}  batch={BATCH}  seq={SEQLEN}  fp32\n")

hdr = (f"{'Depth':>6} | {'Std MiB':>10} {'Std ms':>10} | "
       f"{'Ckpt MiB':>10} {'Ckpt ms':>10} | "
       f"{'Mem saved':>10} {'Time cost':>10}")
print(hdr)
print("-" * len(hdr))

for depth in DEPTHS:
    # Standard
    try:
        s_mem, s_time = run_trial(depth, use_checkpoint=False)
    except RuntimeError as e: # Catch OOM or other runtime errors
        if "out of memory" in str(e).lower():
            s_mem, s_time = float('inf'), float('inf')
        else:
            raise e
        flush()

    # Checkpointed
    try:
        c_mem, c_time = run_trial(depth, use_checkpoint=True)
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            c_mem, c_time = float('inf'), float('inf')
        else:
            raise e
        flush()

    if s_mem < float('inf') and c_mem < float('inf'):
        saved = f"{s_mem - c_mem:+.0f} MiB"
        cost  = f"{c_time/s_time:.2f}x"
    elif s_mem == float('inf') and c_mem < float('inf'):
        saved = "Std OOM!"
        cost  = "—"
    else:
        saved = "Both OOM"
        cost  = "—"

    s_str = f"{s_mem:>10.0f}" if s_mem < float('inf') else f"{'OOM':>10}"
    c_str = f"{c_mem:>10.0f}" if c_mem < float('inf') else f"{'OOM':>10}"
    st_str = f"{s_time*1000:>10.1f}" if s_time < float('inf') else f"{'—':>10}"
    ct_str = f"{c_time*1000:>10.1f}" if c_time < float('inf') else f"{'—':>10}"

    print(f"{depth:>6} | {s_str} {st_str} | {c_str} {ct_str} | {saved:>10} {cost:>10}")

print("\n-- Interpretation --")
print("If O(1) activation memory works, 'Ckpt MiB' should grow SLOWLY")
print("(only weights+gradients scale with depth, not activations).")
print("'Std MiB' should grow FAST (activations + weights + gradients).")
print("'Time cost' is the recomputation overhead — the real price you pay.")
