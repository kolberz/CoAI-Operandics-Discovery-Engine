import sys
import os
sys.path.append(os.getcwd())

import logging
from core.orchestral import LatentState, standard_corridor, EdgeWalkAndDampenLogger
import random

# Configure human-readable logging as requested
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(message)s"))
corridor_logger = logging.getLogger("corridor.telemetry")
corridor_logger.addHandler(handler)
corridor_logger.setLevel(logging.INFO)
corridor_logger.propagate = False # avoid double logging if basicConfig worked

logger = EdgeWalkAndDampenLogger(log_every_step=True)

def simulate_step(state: LatentState) -> LatentState:
    """Simulates a biased random walk in the latent space."""
    return LatentState(
        entropy=max(0.0, state.entropy + random.uniform(-0.2, 0.3)),
        attention_coherence=max(0.0, min(1.0, state.attention_coherence + random.uniform(-0.1, 0.1))),
        embedding_norm=max(0.0, state.embedding_norm + random.uniform(-2.0, 2.0)),
        manifold_divergence=max(0.0, min(1.0, state.manifold_divergence + random.uniform(-0.1, 0.15))),
        centroid_similarity=max(0.0, min(1.0, state.centroid_similarity + random.uniform(-0.1, 0.1)))
    )

def test_orchestral_discovery():
    print("Testing Orchestral AI Discovery Loop (v2 Integrated + Telemetry)...")
    
    orch = standard_corridor(
        entropy_floor=1.0,
        divergence_floor=0.4,
        risk_budget=0.5
    )
    # Inject telemetry and enable dampening for verification
    orch._telemetry = logger
    orch._dampen_enabled = True
    
    initial_state = LatentState(
        entropy=1.5,
        attention_coherence=0.8,
        embedding_norm=10.0,
        manifold_divergence=0.5,
        centroid_similarity=0.3
    )
    
    # Run 20 steps
    print(f"{'Step':<5} | {'Regime':<10} | {'Score':<8} | {'Dominant':<15} | {'Authorized':<10}")
    print("-" * 65)
    
    for outcome in orch.run(initial_state, simulate_step, max_steps=20):
        score = outcome.interestingness.value if outcome.interestingness else 0.0
        signal = outcome.interestingness.dominant_signal if outcome.interestingness else "none"
        print(f"{outcome.step:<5} | {outcome.snapshot.regime.name:<10} | {score:<8.3f} | {signal:<15} | {outcome.authorized:<10}")
        
    # Find best discovery from history
    best_outcome = max(orch._outcomes, key=lambda o: o.interestingness.value if o.interestingness else 0.0)
    
    if best_outcome and best_outcome.interestingness:
        print("\n--- Best Discovery (from Outcome History) ---")
        print(f"Step: {best_outcome.step}")
        print(f"Score: {best_outcome.interestingness.value:.3f}")
        print(f"Dominant Signal: {best_outcome.interestingness.dominant_signal}")
        print(f"Components: {best_outcome.interestingness.components}")
        print(f"State: {best_outcome.state}")
    else:
        print("\nNo discoveries recorded.")

if __name__ == "__main__":
    test_orchestral_discovery()
