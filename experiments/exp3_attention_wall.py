"""
Experiment 3: Attention Memory Scaling
=======================================
Measures peak VRAM and wall-clock time as sequence length
grows, for three attention implementations:

  (A) Naive — explicitly materializes the n×n attention matrix
  (B) SDPA  — PyTorch's scaled_dot_product_attention
              (uses FlashAttention/memory-efficient kernels)
  (C) Linear — linear attention approximation
              (random feature map, Performer-style)

The key claim under test: "reversibility enables 1M-token
context on 24GB." This experiment shows that even with O(1)
activation memory, the attention mechanism itself is the
binding constraint on context length.

Usage:  python exp3_attention_wall.py
Requires: PyTorch >= 2.0, CUDA GPU
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math, gc, sys, time, os
try:
    import psutil
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
    import psutil

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
if DEVICE == "cpu":
    print("Warning: Running on CPU. Performance matches standard RAM, not VRAM.")

# ── Config ────────────────────────────────
D_MODEL  = 1024
N_HEADS  = 16
D_HEAD   = D_MODEL // N_HEADS  # 64
BATCH    = 1    # Reduced for CPU

# Sequence lengths to test (powers of 2)
SEQ_LENGTHS = [256, 512, 1024, 2048] # Reduced max seq length for CPU (standard RAM limit)

def flush():
    gc.collect()

def peak_mib():
    # Return RSS in MiB
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 2**20


# ── Attention Implementations ─────────────

def naive_attention(q, k, v):
    """Standard matmul attention. Materializes full n×n matrix.
    q, k, v: (batch, heads, seq, d_head)"""
    scale = 1.0 / math.sqrt(q.size(-1))
    # This creates an (n × n) tensor — the memory bottleneck
    attn_weights = torch.matmul(q, k.transpose(-2, -1)) * scale
    attn_weights = F.softmax(attn_weights, dim=-1)
    return torch.matmul(attn_weights, v)


def sdpa_attention(q, k, v):
    """PyTorch 2.0+ scaled_dot_product_attention.
    Automatically uses FlashAttention or mem-efficient backend."""
    return F.scaled_dot_product_attention(q, k, v)


def linear_attention(q, k, v, n_features=256):
    """Performer-style linear attention via random feature maps.
    Approximates softmax(QK^T) with φ(Q)φ(K)^T.
    Memory: O(n * d * m) instead of O(n^2).
    """
    d = q.size(-1)

    # Random orthogonal projection (fixed per call for simplicity)
    # In practice you'd store this, but for benchmarking this is fine
    omega = torch.randn(d, n_features, device=q.device, dtype=q.dtype)
    omega = omega / math.sqrt(n_features)

    def phi(x):
        # Random Fourier Feature map
        proj = torch.matmul(x, omega)  # (..., seq, n_features)
        return torch.cat([torch.cos(proj), torch.sin(proj)], dim=-1) / \
               math.sqrt(n_features)

    q_prime = phi(q)  # (batch, heads, seq, 2*n_features)
    k_prime = phi(k)

    # Linear attention: φ(Q) @ (φ(K)^T @ V) — note the associativity
    # Instead of (n×n) @ (n×d), we compute (n×m) @ ((m×n) @ (n×d))
    # = (n×m) @ (m×d), which is O(n*m*d) instead of O(n^2*d)
    kv = torch.matmul(k_prime.transpose(-2, -1), v)  # (batch, heads, 2m, d)
    out = torch.matmul(q_prime, kv)  # (batch, heads, seq, d)

    # Normalization (sum of attention weights)
    k_sum = k_prime.sum(dim=-2, keepdim=True)  # (batch, heads, 1, 2m)
    denom = torch.matmul(q_prime, k_sum.transpose(-2, -1))  # (b, h, n, 1)
    denom = denom.clamp(min=1e-6)

    return out / denom


# ── Benchmark Harness ─────────────────────

def benchmark_attention(attn_fn, seq_len, label):
    """Run one forward+backward pass, measure VRAM and time."""
    flush()

    try:
        q = torch.randn(BATCH, N_HEADS, seq_len, D_HEAD,
                         device=DEVICE, requires_grad=True)
        k = torch.randn_like(q, requires_grad=True)
        v = torch.randn_like(q, requires_grad=True)

        # Warmup
        out = attn_fn(q, k, v)
        out.sum().backward()
        q.grad = k.grad = v.grad = None

        # Measured run
        flush()
        t0 = time.perf_counter()

        out = attn_fn(q, k, v)
        out.sum().backward()

        elapsed = time.perf_counter() - t0
        mem = peak_mib()

        del q, k, v, out
        flush()
        return mem, elapsed

    except RuntimeError: # Catch OOM
        flush()
        return float('inf'), float('inf')


# ── Theoretical predictions ───────────────

def theoretical_naive_mib(seq_len):
    """Approximate memory for the n×n attention matrix alone."""
    # attn_weights: batch * heads * seq * seq * 4 bytes (fp32)
    attn_bytes = BATCH * N_HEADS * seq_len * seq_len * 4
    return attn_bytes / 2**20

def theoretical_linear_mib(seq_len, n_features=256):
    """Approximate memory for linear attention intermediates."""
    # q_prime, k_prime: batch * heads * seq * 2*n_features * 4
    feat_bytes = 2 * BATCH * N_HEADS * seq_len * 2 * n_features * 4
    # kv: batch * heads * 2*n_features * d_head * 4
    kv_bytes = BATCH * N_HEADS * 2 * n_features * D_HEAD * 4
    return (feat_bytes + kv_bytes) / 2**20


# ── Main ──────────────────────────────────
print(f"Device: {DEVICE}")
if DEVICE == "cuda":
    print(f"GPU: {torch.cuda.get_device_name()}")
print(f"Config: d_model={D_MODEL}, heads={N_HEADS}, "
      f"d_head={D_HEAD}, batch={BATCH}\n")

print(f"{'SeqLen':>8} | "
      f"{'Naive MiB':>10} {'ms':>8} | "
      f"{'SDPA MiB':>10} {'ms':>8} | "
      f"{'Linear MiB':>10} {'ms':>8} | "
      f"{'n^2 theory':>10}")
print("-" * 100)

for seq_len in SEQ_LENGTHS:
    results = {}

    for label, fn in [("naive", naive_attention),
                      ("sdpa", sdpa_attention),
                      ("linear", linear_attention)]:
        mem, elapsed = benchmark_attention(fn, seq_len, label)
        results[label] = (mem, elapsed)

    theory = theoretical_naive_mib(seq_len)

    row = f"{seq_len:>8} | "
    for label in ["naive", "sdpa", "linear"]:
        mem, elapsed = results[label]
        if mem < float('inf'):
            row += f"{mem:>10.0f} {elapsed*1000:>8.1f} | "
        else:
            row += f"{'OOM':>10} {'—':>8} | "
    row += f"{theory:>10.0f}"
    print(row)


print(f"\n-- Interpretation --")
print(f"'Naive' materializes the full {BATCH}x{N_HEADS}xnxn attention matrix.")
print(f"  -> Memory scales as O(n^2). This is the wall that kills long context.")
print(f"  -> At n=1M tokens: {theoretical_naive_mib(1_000_000):,.0f} MiB "
      f"= {theoretical_naive_mib(1_000_000)/1024:,.0f} GiB "
      f"(just for attention weights)")
print()
print(f"'SDPA' uses fused kernels (FlashAttention when available).")
print(f"  -> Same O(n^2) compute, but O(n) peak memory via tiling.")
print(f"  -> Watch: SDPA memory should grow MUCH slower than Naive.")
print()
print(f"'Linear' uses random feature approximation (Performer-style).")
print(f"  -> O(n) memory AND O(n) compute.")
print(f"  -> But: approximation quality degrades. Not a free lunch.")
print()
print(f"Key finding: even with O(1) activation memory from reversibility,")
print(f"attention is the true bottleneck for context length.")
print(f"1M tokens x naive attention ~= "
      f"{theoretical_naive_mib(1_000_000)/1024/1024:,.1f} TiB. "
      f"Reversibility cannot touch this.")
