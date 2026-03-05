"""
grounding/self_discovery.py

A "Meta-Discovery" script that uses the Quake-Style primitives to discover
stable structures within a procedural axiom space.

Pipeline:
1. GENERATE: Procedural 'Axioms' via Phantom Mask (#1)
   - 10,000 vectors in 64D space, deterministically seeded.
   
2. SKETCH: Fingerprint via SimHash (P4)
   - Reduce 64D -> 64-bit signature.
   
3. FILTER: Radix-Select (#10) & Confidence-Gate (#12)
   - Find the 'most unique' axioms (maximizing Hamming distance).
   
4. SIMULATE: Symplectic-Shift (N1)
   - Treat selected axioms as particles in an integer lattice.
   - Run physics to find a 'stable orbit' (a consistent system).

5. NORMALIZE: LNS Arithmetic (#5) & L1 Norm (#6)
   - Compute the 'energy' of the system in the log domain.
"""

import math
import time
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import List, Tuple
import multiprocessing

# Import our primitives
from grounding.quake import (
    phantom_hash, splitmix64, simhash_sketch,
    sketch_distance, generate_hyperplanes, fast_reciprocal,
    symplectic_step, lns_from_float, lns_multiply, lns_to_float,
    l1_rms_norm, fast_sigmoid
)

# Configuration
NUM_CANDIDATES = 100000  # Upgraded: Scale up candidates
DIMENSION = 64         # Upgraded: Higher dimensionality space
SKETCH_BITS = 64
SELECTION_SIZE = 10    # Upgraded: Find a larger basis set
SIMULATION_STEPS = 500 # Upgraded: Deeper simulation

def generate_axiom_vector(index: int, dim: int) -> List[float]:
    """Generate a deterministic random vector for an axiom index."""
    vec = []
    for d in range(dim):
        # Use Phantom Hash to generate float in [-1, 1]
        h = phantom_hash(seed=42, layer_id=0, step=index, index=d)
        # Normalize to approx normal distribution
        val = ((h & 0xFFFF) / 32768.0) - 1.0
        vec.append(val)
    return vec

def _generate_and_sketch_worker(args):
    i, dim, planes, sketch_bits = args
    vec = generate_axiom_vector(i, dim)
    s = simhash_sketch(vec, planes, sketch_bits)
    return s

def run_discovery():
    print(f"--- Quake Self-Discovery (Seed=42) ---")
    print(f"Scanning {NUM_CANDIDATES} axioms in {DIMENSION}D space...")
    
    # 1. GENERATE & SKETCH
    # We don't store all vectors (memory efficient), just their sketches.
    planes = generate_hyperplanes(DIMENSION, SKETCH_BITS, seed=1337)
    
    start_time = time.time()
    
    pool_args = [(i, DIMENSION, planes, SKETCH_BITS) for i in range(NUM_CANDIDATES)]
    with multiprocessing.Pool() as pool:
        sketches = pool.map(_generate_and_sketch_worker, pool_args)
        
    print(f"[1] Generated & Sketched {NUM_CANDIDATES} items in {time.time()-start_time:.4f}s")
    
    # 2. FILTER: Find the "Basis Set" (Approximating Orthogonality)
    # We want 5 axioms that are maximally distant from each other.
    # Approach: Greedy selection using bitwise Hamming distance (#10 logic).
    
    # Pick first random axiom
    selected_indices = [0]
    current_sketch = sketches[0]
    
    print(f"[2] Selecting {SELECTION_SIZE} orthogonal basis axioms...")
    for _ in range(SELECTION_SIZE - 1):
        best_dist = -1
        best_idx = -1
        
        # Scan candidates (simulating a "Confidence Gate" #12 for distance)
        for i in range(NUM_CANDIDATES):
            if i in selected_indices: continue
            
            # Compute min distance to ANY selected (max-min diversity)
            min_d = 9999
            for sel in selected_indices:
                d = sketch_distance(sketches[i], sketches[sel])
                if d < min_d: min_d = d
            
            if min_d > best_dist:
                best_dist = min_d
                best_idx = i
        
        selected_indices.append(best_idx)
        print(f"    - Found Axiom #{best_idx} (min_dist={best_dist} bits)")

    # 3. INTERPRET
    print(f"[3] Selected Basis: {selected_indices}")
    basis_vectors = [generate_axiom_vector(i, DIMENSION) for i in selected_indices]
    
    # Normalize them using #6 L1 RMS Norm
    gamma = [1.0] * DIMENSION
    basis_vectors = [l1_rms_norm(v, gamma) for v in basis_vectors]
    
    # 4. SIMULATE: Discover Stability (N1 Symplectic)
    # Mapping:
    #   Particle X,Y = Projections on first 2 dims
    #   Mass = derived from LNS magnitude (#5)
    
    print(f"[4] Simulating System Stability (Symplectic-Shift N1)...")
    
    # Initialize particles on integer lattice
    particles = []
    for i, vec in enumerate(basis_vectors):
        # Map float [-2, 2] to integer [-10000, 10000]
        x = int(vec[0] * 5000)
        y = int(vec[1] * 5000)
        # Velocity from next dims
        vx = int(vec[2] * 100)
        vy = int(vec[3] * 100)
        
        # Mass via LNS (#5)
        mag_lns = lns_from_float(sum(abs(x) for x in vec))
        mass = int(lns_to_float(*mag_lns))
        
        particles.append({'id': selected_indices[i], 'x': x, 'y': y, 'vx': vx, 'vy': vy, 'm': mass})

    # Run simulation
    stable = True
    center_of_mass_drift = 0.0
    
    for t in range(SIMULATION_STEPS):
        # Update everyone relative to origin (center of the 'universe')
        # In a real N-body, we'd sum forces. Here we orbit the "Concept Center" (0,0).
        max_r = 0
        for p in particles:
            nx, ny, nvx, nvy = symplectic_step(p['x'], p['y'], p['vx'], p['vy'], 0, 0, G=1000)
            p['x'], p['y'], p['vx'], p['vy'] = nx, ny, nvx, nvy
            
            r = math.sqrt(nx*nx + ny*ny)
            if r > 50000: stable = False # Escaped
            if r > max_r: max_r = r
            
    print(f"    - Simulation Result: {'STABLE SYSTEM' if stable else 'UNSTABLE/CHAOTIC'}")
    print(f"    - Max Orbital Radius: {max_r:.1f} lattice units")
    
    # 5. DISCOVERY OUTPUT
    if stable:
        print(f"\n[SUCCESS] DISCOVERY: Self-Stabilizing Axiom Set Found")
        print(f"   The axioms {selected_indices} form a coherent logical manifold.")
        # "Hash structure" of the discovery
        discovery_hash = 0
        for idx in selected_indices:
            discovery_hash ^= splitmix64(idx)
        print(f"   Discovery Signature: {hex(discovery_hash)}")
    else:
        print(f"\n[FAILURE] CONVERGENCE FAILURE: Axioms are incoherent.")

if __name__ == "__main__":
    run_discovery()
