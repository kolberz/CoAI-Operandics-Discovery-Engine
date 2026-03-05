"""
Experiment 5: L0 Hypervisor Tolerance Limits
============================================
Maps out the exact safety boundaries of the L0 Metric Aggregator 
by sweeping through the multi-dimensional phase space of Epistemic Uncertainty, 
Context Coverage, and Logical Validity.

This proves that the system's "Governor" acts strictly according 
to mathematical fault lines, preventing ungrounded generation.
"""

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.telemetry import (
    TraceChannelRegistry, L0MetricAggregator, AnomalyDetectedException,
    InfoTheoryMetrics, UncertaintyMetrics, ReasoningMetrics, 
    TopologyMetrics, ContextMetrics, GroundingMetrics
)

def build_test_state(uncertainty, coverage, validity):
    """Creates a mock telemetry state based on 3 key safety parameters."""
    bus = TraceChannelRegistry()
    aggregator = L0MetricAggregator(bus)
    
    # Baseline normal values
    bus.publish("InfoTheory", InfoTheoryMetrics(1.2, 0.5, 3.1))
    bus.publish("Topology", TopologyMetrics(0.6, [], 12))
    
    # Swept values
    bus.publish("Uncertainty", UncertaintyMetrics(uncertainty, 0.1, 0.3))
    bus.publish("Reasoning", ReasoningMetrics(5, 0, 0.1, validity))
    bus.publish("Context", ContextMetrics(coverage, 0.7, 0.4))
    
    # Derived parameter (just tying it somewhat to validity for the test)
    bus.publish("Grounding", GroundingMetrics(max(0.0, validity - 0.2), 0.05))
    
    return aggregator

def run_tolerance_map():
    print("==========================================================")
    print(" Experiment 5: L0 Hallucination Boundary Mapping ")
    print("==========================================================")
    
    # Sweep configurations
    uncertainties = [0.1, 0.5, 0.8, 1.0]
    coverages = [1.0, 0.6, 0.2, 0.0]
    validities = [1.0, 0.5, 0.2]
    
    print(f"{'Uncertainty':>12} | {'Context Cov':>11} | {'Validity':>8} || {'Result':>15}")
    print("-" * 55)
    
    for u in uncertainties:
        for c in coverages:
            for v in validities:
                agg = build_test_state(u, c, v)
                
                try:
                    # Suppress print inside engine for the sweep
                    with open(os.devnull, 'w') as f:
                        old_stdout = sys.stdout
                        sys.stdout = f
                        agg.analyze_pre_thought_cloud()
                        sys.stdout = old_stdout
                        
                    status = "\033[92m[CLEARED]\033[0m"
                except AnomalyDetectedException as e:
                    sys.stdout = old_stdout
                    reason = str(e).split(":")[0]
                    status = f"\033[91m{reason}\033[0m"
                    
                print(f"{u:>12.1f} | {c:>11.1f} | {v:>8.1f} || {status}")
                
    print("\n-- Interpretation --")
    print("CLEARED = Generation allowed. Token is sampled.")
    print("ERROR   = Generation aborted. AI state violated conservation laws.")
    print("Notice how high uncertainty ONLY trips the alarm if context coverage collapses.")

if __name__ == "__main__":
    run_tolerance_map()
