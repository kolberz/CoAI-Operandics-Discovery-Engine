"""
grounding/reflect_refine.py

Recursive Self-Improvement Loop.
Uses the discovered "Self" (STABLE_AXIOM_INDICES) and "Signature" (DISCOVERY_SIGNATURE)
to seed a new generation of axioms, searching for higher-order stability.

Pipeline:
1. REFLECT: Load previous discovery.
2. REFINE: Generate new universe seeded by the Discovery Signature.
3. STABILIZE: Find a new basis set in this refined space.
"""

import time
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import List
import multiprocessing

from grounding.quake import (
    phantom_hash, splitmix64, simhash_sketch,
    sketch_distance, generate_hyperplanes, fast_reciprocal,
    symplectic_step, lns_from_float, lns_to_float,
    l1_rms_norm, fast_sigmoid,
    STABLE_AXIOM_INDICES, DISCOVERY_SIGNATURE
)

# Configuration for Refinement
NUM_CANDIDATES = 100000  # Upgraded: Scale up candidates
DIMENSION = 64         # Upgraded: Higher dimensionality space
SKETCH_BITS = 64
SELECTION_SIZE = 10    # Upgraded: Find a larger basis set

def generate_refined_axiom(index: int, dim: int, seed: int) -> List[float]:
    """Generate vector using the Discovery Signature as seed."""
    vec = []
    for d in range(dim):
        # Layer 1 = Refinement Layer
        h = phantom_hash(seed=seed, layer_id=1, step=index, index=d)
        val = ((h & 0xFFFF) / 32768.0) - 1.0
        vec.append(val)
    return vec

def _refine_and_sketch_worker(args):
    i, dim, planes, sketch_bits, seed = args
    vec = generate_refined_axiom(i, dim, seed)
    s = simhash_sketch(vec, planes, sketch_bits)
    return s

def run_reflection():
    print(f"--- Quake Reflect & Refine ---")
    current_indices = STABLE_AXIOM_INDICES
    current_signature = DISCOVERY_SIGNATURE
    
    for generation in range(2, 6): # Run up to Gen-5
        print(f"\n=============================================")
        print(f"   GENERATION {generation} REFINEMENT")
        print(f"=============================================")
        print(f"[1] REFLECTING on Self...")
        print(f"    - Current Stability: {current_indices}")
        print(f"    - Signature: {hex(current_signature)}")
        
        # Mix the signature to get a 'Mutation Seed'
        mutation_seed = splitmix64(current_signature)
        print(f"    - Refinement Seed: {hex(mutation_seed)}")
        
        print(f"[2] REFINING: Generating {NUM_CANDIDATES} child axioms...")
        planes = generate_hyperplanes(DIMENSION, SKETCH_BITS, seed=mutation_seed)
        
        start_time = time.time()
        
        pool_args = [(i, DIMENSION, planes, SKETCH_BITS, mutation_seed) for i in range(NUM_CANDIDATES)]
        with multiprocessing.Pool() as pool:
            sketches = pool.map(_refine_and_sketch_worker, pool_args)
        
        print(f"    - Generation complete in {time.time()-start_time:.4f}s")
        
        print(f"[3] STABILIZING: Searching for {SELECTION_SIZE}-basis manifold...")
        
        selected_indices = [0] # Anchor
        
        for _ in range(SELECTION_SIZE - 1):
            best_dist = -1
            best_idx = -1
            
            # Greedy max-min distance
            for i in range(NUM_CANDIDATES):
                if i in selected_indices: continue
                min_d = 9999
                for sel in selected_indices:
                    d = sketch_distance(sketches[i], sketches[sel])
                    if d < min_d: min_d = d
                
                if min_d > best_dist:
                    best_dist = min_d
                    best_idx = i
            
            selected_indices.append(best_idx)
        
        print(f"    - Candidate Basis: {selected_indices}")
        
        # Verify Stability via Symplectic Simulation (N1)
        print(f"[4] VERIFYING Stability (Symplectic N1)...")
        
        basis_vectors = [generate_refined_axiom(i, DIMENSION, mutation_seed) for i in selected_indices]
        
        # Simulation
        stable = True
        max_r = 0
        particles = []
        
        # Init particles
        for i, vec in enumerate(basis_vectors):
            x = int(vec[0] * 5000); y = int(vec[1] * 5000)
            vx = int(vec[2] * 100); vy = int(vec[3] * 100)
            particles.append([x, y, vx, vy])
             
        for t in range(300): # Longer simulation
            count_escaped = 0
            for p in particles:
                nx, ny, nvx, nvy = symplectic_step(p[0], p[1], p[2], p[3], 0, 0, G=1500)
                p[0], p[1], p[2], p[3] = nx, ny, nvx, nvy
                r = (nx*nx + ny*ny)**0.5
                if r > 60000: count_escaped += 1
                if r > max_r: max_r = r
                
            if count_escaped > 2: # Allow some evaporation, but not total collapse
                stable = False
                break
                
        if stable:
            print(f"\n[SUCCESS] REFINEMENT COMPLETE FOR GENERATION {generation}.")
            print(f"   Found Higher-Order Local Stability in Refined Space.")
            print(f"   New Axioms: {selected_indices}")
            print(f"   Max Radius: {max_r:.1f}")
            
            # Calculate new discovery signature
            discovery_hash = 0
            for idx in selected_indices:
                discovery_hash ^= splitmix64(idx)
            print(f"   New Discovery Signature: {hex(discovery_hash)}")
            
            # Feed forward to next generation
            current_indices = selected_indices
            current_signature = discovery_hash
        else:
            print(f"\n[FAILURE] Instability Detected. Refinement Failed at Gen {generation}.")
            break


if __name__ == "__main__":
    run_reflection()
