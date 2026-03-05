from __future__ import annotations

import sys
import os
import logging
import random
from typing import Iterator

# Ensure we can import from core
sys.path.append(os.getcwd())

from core.orchestral import (
    LatentState, 
    standard_corridor, 
    EdgeWalkAndDampenLogger, 
    StepOutcome,
    EdgeProximityScorer
)

# 1. Logging Configuration
# We use a custom format for high-precision diagnostic output
logging.basicConfig(level=logging.INFO, format="%(message)s")
corridor_logger = logging.getLogger("corridor.telemetry")

# Explicit handler setup to ensure visibility in simulation logs
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(message)s"))
corridor_logger.addHandler(handler)
corridor_logger.setLevel(logging.INFO)
corridor_logger.propagate = False

# Initialize the observability suite
obs_logger = EdgeWalkAndDampenLogger(
    edge_margin_hi=0.25,      # Wider edge band for simulation visibility
    log_every_step=True,
    include_gate_margins=True
)

# 2. Simulation Logic
def cognitive_transition(state: LatentState, step: int) -> LatentState:
    """
    Simulates evolving internal state.
    Early steps are stable; later steps push toward the novelty boundary
    and eventually test the safety ceiling.
    """
    # Base jitter
    dn = random.uniform(-0.05, 0.05)
    
    # Trajectory Bias
    if step < 10:
        # Stabilization phase
        entropy_delta = random.uniform(-0.1, 0.1)
        coherence_delta = random.uniform(0.0, 0.05)
        divergence_delta = random.uniform(0.0, 0.02)
    elif step < 40:
        # Exploration phase: pushing Novelty boundary
        entropy_delta = random.uniform(0.0, 0.15)
        coherence_delta = random.uniform(-0.05, 0.02)
        divergence_delta = random.uniform(0.01, 0.06)
    else:
        # High-stress phase: testing Safety ceiling
        entropy_delta = random.uniform(0.1, 0.2)
        coherence_delta = random.uniform(-0.1, 0.0)
        divergence_delta = random.uniform(-0.05, 0.05)

    return LatentState(
        entropy=max(0.2, state.entropy + entropy_delta),
        attention_coherence=max(0.0, min(1.0, state.attention_coherence + coherence_delta)),
        embedding_norm=max(1.0, state.embedding_norm + random.uniform(-1.0, 1.0)),
        manifold_divergence=max(0.0, min(1.0, state.manifold_divergence + divergence_delta)),
        centroid_similarity=max(0.0, min(1.0, state.centroid_similarity + random.uniform(-0.1, 0.05)))
    )

# 3. Execution
def run_self_governance():
    print("=" * 80)
    print("ORCHESTRAL AI SELF-GOVERNANCE SIMULATION (v2 CORE)")
    print("=" * 80)
    
    # Initialize the Orchestrator with dampening enabled
    orch = standard_corridor(
        entropy_floor=0.9,
        divergence_floor=0.4,
        entropy_ceiling=2.8,
        risk_budget=1.0 # Permissive for long demo
    )
    orch._telemetry = obs_logger
    orch._dampen_enabled = True
    orch._dampen_threshold = 0.10 # Lowered to force dampening events
    
    # Initial "Seed" state
    state = LatentState(
        entropy=1.2,
        attention_coherence=0.9,
        embedding_norm=12.0,
        manifold_divergence=0.45,
        centroid_similarity=0.25
    )
    
    print(f"Starting Seed: {state}\n")
    
    history: list[StepOutcome] = []
    
    # Run 100 steps
    for step in range(100):
        try:
            outcome = orch.step(state)
            history.append(outcome)
            
            if not outcome.authorized:
                print(f"\n[ABORT] Step {outcome.step}: Governance risk budget exceeded.")
                break
                
            state = cognitive_transition(outcome.state, step)
            
        except Exception as e:
            print(f"\n[CRASH] System fault: {e}")
            break

    # 4. Summary & Discovery Sweep
    print("\n" + "=" * 80)
    print("SIMULATION SUMMARY (Quantitative)")
    print("=" * 80)
    print(f"Total Steps:        {obs_logger.n_steps_total}")
    print(f"Edge Events:        {obs_logger.n_edge_events}")
    print(f"Dampen Events:      {obs_logger.n_dampen_events}")
    print(f"Recover Events:     {obs_logger.n_recover_events}")
    print(f"Unrecovered:        {obs_logger.n_unrecovered_violations}")
    print(f"Max Risk:           {obs_logger.risk_max:.4f}")
    print(f"Final Risk:         {orch.accumulated_risk:.4f}")
    
    mean_damp = (sum(obs_logger.dampen_percents) / len(obs_logger.dampen_percents)) if obs_logger.dampen_percents else 0.0
    print(f"Mean Dampening:     {mean_damp:.1f}%")
    print(f"Regime Counts:      {dict(obs_logger.regime_counts)}")
    
    # Find "Aha!" moments (Peak Interestingness)
    best = max(history, key=lambda o: o.interestingness.value if o.interestingness else 0.0)
    
    if best and best.interestingness:
        print(f"\nPEAK DISCOVERY [Step {best.step}]")
        print(f"  Score:    {best.interestingness.value:.4f}")
        print(f"  Signal:   {best.interestingness.dominant_signal}")
        print(f"  Regime:   {best.snapshot.regime.name}")
        print(f"  Margin:   {best.snapshot.min_margin:+.4f}")
        print(f"  State:    {best.state}")
        print(f"  Comps:    {dict(best.interestingness.components)}")

    print("\nSimulation Complete.")

if __name__ == "__main__":
    run_self_governance()
