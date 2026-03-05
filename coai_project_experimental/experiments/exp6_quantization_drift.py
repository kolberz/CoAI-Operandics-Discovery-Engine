import sys
import os

# Add the project root to sys.path so we can run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np
import time

def quantization_drift_experiment(max_depth=200, n_trials=1000):
    """
    Measure when INT8 computation diverges from BF16 ground truth.
    
    Theory predicts: variance ~ sqrt(depth) * quantization_step
    Critical depth where signature matching fails:
        depth_crit ≈ (tolerance / quantization_step)^2
    
    INT8 step = 1/128 ≈ 0.0078
    BF16 step ≈ 2^{-7} * 2^{-3} ≈ 0.00098 (for values near 1.0)
    
    If tolerance = 0.01 (1% relative error):
        INT8 critical depth ≈ (0.01 / 0.0078)^2 ≈ 1.6 layers (!)
        BF16 critical depth ≈ (0.01 / 0.00098)^2 ≈ 104 layers
    """
    results = {}
    
    for precision in ['int8', 'bf16', 'fp32']:
        step = {'int8': 1/128, 'bf16': 1/1024, 'fp32': 2**-23}[precision]
        
        drift_by_depth = []
        # Seed outside to keep sequence consistent per precision
        np.random.seed(42)
        
        x_exact = np.ones(n_trials)
        x_quant = np.ones(n_trials)
        
        for depth in range(1, max_depth + 1):
            weight = np.random.randn(n_trials) * 0.1 + 1.0  # Near-identity
            x_exact *= weight
            x_quant = np.round(x_quant * weight / step) * step  # Quantize
            
            errors = np.abs(x_exact - x_quant) / np.maximum(np.abs(x_exact), 1e-10)
            
            drift_by_depth.append({
                'depth': depth,
                'mean_relative_error': np.mean(errors),
                'std_relative_error': np.std(errors),
                'max_relative_error': np.max(errors),
                'exceeds_1pct': np.mean(errors > 0.01),
            })
        
        results[precision] = drift_by_depth
        
        # Find critical depth
        critical = next(
            (d['depth'] for d in drift_by_depth if d['exceeds_1pct'] > 0.5), 
            None
        )
        print(f"[{precision.upper()}] critical depth (50% of trials > 1% error) = {critical}")
    
    return results

if __name__ == "__main__":
    print("--- Starting Quantization Drift Physics Experiment ---")
    start_time = time.time()
    res = quantization_drift_experiment(max_depth=150, n_trials=1000)
    print(f"--- Completed in {time.time() - start_time:.2f}s ---")
