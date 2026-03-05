"""
experiments/attention_memory.py (v3.2)
Reproducible benchmark for validating the DIM_INFO (memory) limits 
used in the CoAI Economic/Value parameters.
"""
import torch
import tracemalloc
import sys

def measure_attention_memory(seq_len: int, d_model: int = 512, use_sdpa: bool = False):
    """Measures peak VRAM/RAM allocation for a single attention forward pass."""
    tracemalloc.start()
    
    # Use CPU since CUDA is not available in the environment
    device = "cpu"
    
    q = torch.randn(1, 8, seq_len, d_model // 8, device=device)
    k = torch.randn(1, 8, seq_len, d_model // 8, device=device)
    v = torch.randn(1, 8, seq_len, d_model // 8, device=device)
    
    if use_sdpa:
        out = torch.nn.functional.scaled_dot_product_attention(q, k, v)
    else:
        # Standard scaled dot product attention
        scale = d_model ** -0.5
        scores = torch.matmul(q, k.transpose(-2, -1)) * scale
        attn = torch.softmax(scores, dim=-1)
        out = torch.matmul(attn, v)
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / (1024 * 1024)  # Return MiB

if __name__ == "__main__":
    print("--- CoAI Validation: Attention Memory Scaling ---")
    print(f"{'n (Seq Len)':<12} | {'Naive (MiB)':<12} | {'SDPA (MiB)':<12} | {'Ratio':<10}")
    print("-" * 55)
    for seq_len in [4096, 8192, 16384]:
        try:
            naive = measure_attention_memory(seq_len, use_sdpa=False)
            sdpa = measure_attention_memory(seq_len, use_sdpa=True)
            print(f"{seq_len:<12d} | {naive:<12.1f} | {sdpa:<12.1f} | {naive/sdpa:<10.1f}x")
        except Exception as e:
            print(f"{seq_len:<12d} | FAILED: {str(e)}")
