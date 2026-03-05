"""
main_grounded.py

Entry point for the physically grounded CoAI discovery system.
Runs the algebraic engine, then validates against SENTINEL gates.

This demonstrates the integration of:
  - Algebraic theorem discovery (Layers 1-4)
  - Physical grounding (Layer 5: Landauer bridge)
  - Uncertainty propagation (Layer 5: interval arithmetic)
  - Causal analysis (Layer 5: do-calculus)
  - Migration planning (Layer 6: transport)
  - Audit validation (Layer 7: SENTINEL)
"""

import sys
import time

from core.logic import MODULE, REAL, Variable, Constant, Function, Forall, Equality
from discovery.engine import CoAIOperandicsExplorer
from grounding.dimensions import (
    DimensionalChecker, DimensionRegistry, LandauerBridge,
    DIMENSIONLESS, ENERGY, BITS, LANDAUER_LIMIT
)
from grounding.intervals import (
    Interval, ModuleMeasurement, IntervalPropagator,
    iv_max, iv_min
)
from grounding.causal import CausalModel
from grounding.transport import TransportModel, SystemProfile
from grounding.sentinel import SentinelAuditor


def create_example_measurements() -> list:
    """
    Create realistic module measurements for demonstration.
    These represent a hypothetical microservice architecture.
    """
    auth = ModuleMeasurement(
        name="AuthService",
        risk=Interval.measured(0.02, 0.005, DIMENSIONLESS),
        cost=Interval.measured(1.5e-8, 3e-9, ENERGY),     # ~15 nJ
        security=Interval.measured(128.0, 5.0, BITS),       # 128-bit keys
        complexity=Interval.measured(450.0, 20.0, BITS),     # ~450 bits of state
    )
    
    db = ModuleMeasurement(
        name="DatabaseQuery",
        risk=Interval.measured(0.05, 0.01, DIMENSIONLESS),
        cost=Interval.measured(5.0e-8, 1e-8, ENERGY),      # ~50 nJ
        security=Interval.measured(64.0, 3.0, BITS),        # 64-bit encryption
        complexity=Interval.measured(800.0, 50.0, BITS),     # ~800 bits of state
    )
    
    cache = ModuleMeasurement(
        name="CacheLayer",
        risk=Interval.measured(0.01, 0.003, DIMENSIONLESS),
        cost=Interval.measured(2.0e-9, 5e-10, ENERGY),     # ~2 nJ
        security=Interval.measured(32.0, 2.0, BITS),        # 32-bit hashes
        complexity=Interval.measured(200.0, 10.0, BITS),     # ~200 bits
    )
    
    return [auth, db, cache]


def create_example_profiles(measurements: list) -> list:
    """Create system profiles for migration planning."""
    
    # Current architecture: sequential monolith
    monolith = SystemProfile(
        name="Monolith (Seq)",
        modules=measurements,
        topology="sequential"
    )
    
    # Target architecture: parallel microservices  
    # (Same modules but different composition)
    microservices = SystemProfile(
        name="Microservices (Par)",
        modules=measurements,
        topology="parallel"
    )
    
    return [monolith, microservices]


def run_algebraic_discovery():
    """Phase 1: Run the algebraic theorem discovery engine."""
    print("\n" + "=" * 60)
    print("  PHASE 1: ALGEBRAIC DISCOVERY")
    print("=" * 60)
    
    explorer = CoAIOperandicsExplorer(
        max_clauses=200,
        max_depth=4,
        min_interestingness=0.15
    )
    
    print(f"\n  Initialized with {len(explorer.axioms)} axioms")
    
    # Run discovery
    session = explorer.discover_and_verify_conjectures(
        cumulative=True,
        max_cycles=2,
        verbose=True
    )
    
    return explorer, session


def run_dimensional_analysis(explorer):
    """Phase 2: Check dimensional consistency of axiom set."""
    print("\n" + "=" * 60)
    print("  PHASE 2: DIMENSIONAL ANALYSIS")
    print("=" * 60)
    
    checker = DimensionalChecker()
    
    # Collect axiom names from the engine
    names = [f"axiom_{i}" for i in range(len(explorer.axioms))]
    
    report = checker.check_axiom_set(explorer.axioms, names)
    
    print(f"\n  Checked {report.checked} axioms")
    print(f"  Verdict: {report.verdict}")
    
    if report.inferred_dims:
        print(f"  Inferred {len(report.inferred_dims)} variable dim(s):")
        for vname, dim in sorted(report.inferred_dims.items()):
            print(f"    {vname} -> {dim}")
    
    if report.unknown_required > 0:
        print(f"  Unknown required: {report.unknown_required} "
              f"(blocks deployment)")
    if report.unknown_coverage > 0:
        print(f"  Unknown coverage: {report.unknown_coverage} "
              f"(warning only)")
        if hasattr(report, 'coverage_sample') and report.coverage_sample:
            print(f"    Sample: {', '.join(report.coverage_sample)} ...")
    if report.unknown_constants:
        print(f"  Unregistered constants: "
              f"{', '.join(sorted(report.unknown_constants))}")
    
    if report.errors:
        print(f"\n  Found {len(report.errors)} dimensional issues:")
        for err in report.errors:
            print(f"    {err.axiom_name}: {err.message}")
        
        print("\n  Applying Landauer Bridge...")
        bridge = LandauerBridge()
        print(f"  {bridge.report()}")
        
        bridge_axioms = bridge.generate_bridge_axioms()
        print(f"\n  Generated {len(bridge_axioms)} bridge axioms:")
        for formula, name, classification in bridge_axioms:
            print(f"    {name} [{classification}]")
    else:
        print("  All axioms dimensionally consistent")
    
    return report


def run_interval_propagation(measurements):
    """Phase 3: Propagate uncertainty through compositions."""
    print("\n" + "=" * 60)
    print("  PHASE 3: UNCERTAINTY PROPAGATION")
    print("=" * 60)
    
    prop = IntervalPropagator()
    
    print("\n  Input measurements:")
    for m in measurements:
        print(f"    {m.summary()}")
        print()
    
    # Sequential composition: Auth -> DB
    seq_result = prop.seq(measurements[0], measurements[1])
    print(f"  Sequential {measurements[0].name} -> {measurements[1].name}:")
    print(f"    {seq_result.summary()}")
    
    # Parallel composition: (Auth || Cache) with Dep=0.3
    par_result = prop.par(measurements[0], measurements[2], dep=0.3)
    print(f"\n  Parallel {measurements[0].name} || {measurements[2].name} (Dep=0.3):")
    print(f"    {par_result.summary()}")
    
    # Full pipeline: Seq(Par(Auth, Cache), DB)
    full = prop.seq(par_result, measurements[1])
    print(f"\n  Full pipeline: Seq(Par(Auth,Cache), DB):")
    print(f"    {full.summary()}")
    
    # Validate Quad-Goal
    print(f"\n  Quad-Goal Validation:")
    bridge = LandauerBridge()
    for m in measurements + [seq_result, par_result, full]:
        qg = prop.validate_quad_goal(m, bridge.landauer_factor)
        print(f"    {qg['module']}: {qg['message']}")
    
    return full


def run_causal_analysis():
    """Phase 4: Analyze causal scope."""
    print("\n" + "=" * 60)
    print("  PHASE 4: CAUSAL ANALYSIS")
    print("=" * 60)
    
    model = CausalModel()
    print(f"\n{model.report()}")
    
    # Audit specific theorems
    print("\n  Theorem Causal Audits:")
    
    audits = [
        model.audit_theorem(
            "Parallel Optimization Bound",
            ["composition_type"], ["cost"]
        ),
        model.audit_theorem(
            "Quad-Goal Constraint",
            ["risk"], ["cost"]  # risk is NOT intervenable!
        ),
        model.audit_theorem(
            "Security Non-Commutativity",
            ["filter_placement"], ["security"]
        ),
        model.audit_theorem(
            "Ineffective Redundancy",
            ["redundancy_level"], ["risk"]
        ),
    ]
    
    for a in audits:
        status = "CAUSAL" if a["causal_validity"] else "CORRELATIONAL"
        print(f"\n    {a['theorem']}: {status}")
        if a["issues"]:
            for issue in a["issues"]:
                print(f"      ! {issue}")
        print(f"      {a['recommendation']}")


def run_migration_planning(profiles):
    """Phase 5: Plan system migration."""
    print("\n" + "=" * 60)
    print("  PHASE 5: MIGRATION PLANNING")
    print("=" * 60)
    
    transport = TransportModel()
    
    if len(profiles) >= 2:
        plan = transport.plan_migration(profiles[0], profiles[1])
        print(f"\n{transport.report(plan)}")
    else:
        print("  Insufficient profiles for migration planning")


def run_sentinel_audit(explorer, measurements, profiles):
    """Phase 6: Full SENTINEL audit."""
    print("\n" + "=" * 60)
    print("  PHASE 6: SENTINEL v2.0 AUDIT")
    print("=" * 60)
    
    auditor = SentinelAuditor()
    
    names = [f"axiom_{i}" for i in range(len(explorer.axioms))]
    
    report = auditor.full_audit(
        axioms=explorer.axioms,
        axiom_names=names,
        measurements=measurements,
        system_profiles=profiles
    )
    
    print(report.summary)
    
    return report


def main():
    start = time.time()
    
    print("=" * 60)
    print("  CoAI OPERANDICS: GROUNDED DISCOVERY ENGINE")
    print("  Layers 1-7: Algebra -> Physics -> Deployment")
    print("=" * 60)
    
    # Phase 1: Algebraic discovery
    explorer, session = run_algebraic_discovery()
    
    # Phase 2: Dimensional analysis
    dim_errors = run_dimensional_analysis(explorer)
    
    # Phase 3: Create measurements and propagate uncertainty
    measurements = create_example_measurements()
    composed = run_interval_propagation(measurements)
    
    # Phase 4: Causal analysis
    run_causal_analysis()
    
    # Phase 5: Migration planning
    profiles = create_example_profiles(measurements)
    run_migration_planning(profiles)
    
    # Phase 6: SENTINEL audit
    report = run_sentinel_audit(explorer, measurements, profiles)
    
    elapsed = time.time() - start
    
    print(f"\n{'=' * 60}")
    print(f"  Total runtime: {elapsed:.1f}s")
    print(f"  Deployment gate: {'PASSED' if report.overall_passed else 'NOT PASSED'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
