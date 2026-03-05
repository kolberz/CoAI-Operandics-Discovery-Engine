"""
Experiment 2: Fixed-Point Depth Divergence
==========================================
Train a deep residual network on a simple regression task.
After each layer, quantize activations to K-bit fixed point
with stochastic rounding (straight-through estimator for gradients).

Sweep over bit-depths and network depths.
Measure: does training converge? What is the final loss?

This tests the claim that "64-bit fixed-point preserves gradient
fidelity over 10,000+ layers" by checking much smaller depths first.

Usage: python exp2_fixedpoint.py
"""

import torch
import torch.nn as nn
import math, sys

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
HIDDEN = 256
BATCH  = 16   # Reduced from 64 for CPU
STEPS  = 200  # Reduced from 2000 for CPU
LR     = 1e-3

BIT_DEPTHS    = [8, 12, 16, 24, 32]  # 32 = full float32 (baseline)
LAYER_DEPTHS  = [4, 8, 16] # Reduced from [4, 16, 64, 256] for CPU

if DEVICE == "cpu":
    print("Warning: Running on CPU. Steps reduced to 200. Results may not fully converge.")


class STE_Quantize(torch.autograd.Function):
    """Fixed-point quantize with stochastic rounding.
    Forward: quantized value.  Backward: straight-through (identity)."""
    @staticmethod
    def forward(ctx, x, bits):
        if bits >= 32:
            return x
        qmax = 2**(bits - 1) - 1
        # Per-tensor symmetric quantization
        amax = x.detach().abs().max().clamp(min=1e-12)
        scale = qmax / amax
        x_scaled = x * scale
        # Stochastic rounding
        floor_val = x_scaled.floor()
        frac = x_scaled - floor_val
        rounded = floor_val + (torch.rand_like(frac) < frac).to(x.dtype)
        rounded = rounded.clamp(-qmax, qmax)
        return rounded / scale

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output, None  # straight-through


def quantize(x, bits):
    return STE_Quantize.apply(x, bits)


class QBlock(nn.Module):
    """Residual block with post-activation quantization."""
    def __init__(self, d, bits):
        super().__init__()
        self.fc1  = nn.Linear(d, d)
        self.fc2  = nn.Linear(d, d)
        self.bits = bits
        # Small init to prevent explosion in very deep nets
        nn.init.xavier_uniform_(self.fc1.weight, gain=0.1)
        nn.init.xavier_uniform_(self.fc2.weight, gain=0.1)
        nn.init.zeros_(self.fc1.bias)
        nn.init.zeros_(self.fc2.bias)

    def forward(self, x):
        h = torch.nn.functional.gelu(self.fc1(x))
        h = x + self.fc2(h) * (1.0 / math.sqrt(self.num_layers))
        return quantize(h, self.bits)


class QNet(nn.Module):
    def __init__(self, d, depth, bits):
        super().__init__()
        self.blocks = nn.ModuleList()
        for _ in range(depth):
            blk = QBlock(d, bits)
            blk.num_layers = depth  # for scaling
            self.blocks.append(blk)
        self.head = nn.Linear(d, d, bias=False)

    def forward(self, x):
        for b in self.blocks:
            x = b(x)
        return self.head(x)


def run_experiment(depth, bits):
    """Train QNet to approximate a random linear target. Return final MSE."""
    torch.manual_seed(42)

    # Target: a fixed random projection
    target_w = torch.randn(HIDDEN, HIDDEN, device=DEVICE) / math.sqrt(HIDDEN)

    model = QNet(HIDDEN, depth, bits).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=LR)

    losses = []
    for step in range(STEPS):
        x = torch.randn(BATCH, HIDDEN, device=DEVICE)
        y_target = x @ target_w
        y_pred = model(x)
        loss = nn.functional.mse_loss(y_pred, y_target)

        if torch.isnan(loss) or torch.isinf(loss):
            return float('nan'), True  # diverged

        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

        if step % 500 == 0:
            losses.append(loss.item())

    return losses[-1], False


# ── Main ──────────────────────────────────
print(f"Device: {DEVICE}")
print(f"Task: learn random projection, hidden={HIDDEN}, "
      f"batch={BATCH}, steps={STEPS}\n")

# Header
bits_header = "".join(f"{'  ' + str(b) + '-bit':>12}" for b in BIT_DEPTHS)
print(f"{'Depth':>8} |{bits_header}")
print("-" * (10 + 12 * len(BIT_DEPTHS)))

for depth in LAYER_DEPTHS:
    row = f"{depth:>8} |"
    for bits in BIT_DEPTHS:
        try:
            final_loss, diverged = run_experiment(depth, bits)
            if diverged:
                row += f"{'DIVERGED':>12}"
            elif final_loss > 1.0:
                row += f"{'FAILED':>12}"
            else:
                row += f"{final_loss:>12.4f}"
        except RuntimeError: # Catch OOM
            row += f"{'OOM':>12}"
            pass
    print(row)

print()
print("-- Interpretation --")
print("Cells show final MSE loss (lower = better).")
print("'DIVERGED' = loss hit NaN/Inf (quantization noise overwhelmed signal).")
print("'FAILED'   = converged but poorly (loss > 1.0).")
print()
print("Key question: for a given depth, what is the minimum bit-depth")
print("that still converges? Does 64-bit always work? Does 16-bit break")
print("at deep networks? The sqrt(N) variance growth predicts that")
print("lower bit-depths fail at shallower networks.")
