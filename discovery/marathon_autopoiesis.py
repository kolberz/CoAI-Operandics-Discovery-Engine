"""
discovery/marathon_autopoiesis.py

Infinite "God Mode" Discovery entry point. 
Disables budgetary and equilibrium ceilings.
Active Autopoietic Metasystem for inter-cycle heuristic mutation.
"""

import os
import math
import time
import sys
from discovery.engine import DiscoveryEngine

def run_marathon():
    print("\n" + "#"*60)
    print("  COAI OPERANDICS DISCOVERY ENGINE: MARATHON MODE active")
    print("  Mode: INF-BUDGET | INF-EQUILIBRIUM | AUTOPOIESIS-ON")
    print("#" + "="*58 + "#\n")

    # 1. Setup Environment for "God Mode"
    os.environ["COAI_BETA_BUDGET"] = "inf"
    os.environ["COAI_MCTS_ITERS"] = "500" # High initial baseline
    os.environ["COAI_CERTIFIED_MODE"] = "1" # Always verify against Lean

    # 2. Initialize Engine
    engine = DiscoveryEngine(
        max_clauses=2000,   # Higher starting point
        max_depth=10,       # Deeper search
        min_interestingness=0.05 # Even wider net
    )

    # 3. Warm Start: Inject proved lemmas from Cycle 0-30
    from core.logic import Forall, Equality, Function, Constant, Variable, MODULE, REAL, Implies
    from discovery.engine import ID_M, R_ZERO, DEP_ZERO
    
    m1 = Variable("M1", MODULE)
    m2 = Variable("M2", MODULE)
    
    # -- Learned in Run 1 (Algebraic) --
    # Lemma 1: Par_Dyn(ID_M, M1) = M1
    engine.lemmas.append(Forall(m1, Equality(Function("Par_Dyn", [ID_M, m1]), m1)))
    # Lemma 2: Ent(Par_Dyn(ID_M, M1)) = Ent(M1)
    engine.lemmas.append(Forall(m1, Equality(
        Function("Ent", [Function("Par_Dyn", [ID_M, m1])], sort=REAL), 
        Function("Ent", [m1], sort=REAL)
    )))
    
    # -- Learned in Run 2 (Resource Oracles) --
    # Lemma 3: Resource neutrality of Seq with identity
    # Forall M1, M2. ResourceCost(M2) = R_ZERO -> ResourceCost(Seq(M1, M2)) = ResourceCost(M1)
    engine.lemmas.append(Forall([m1, m2], Implies(
        Equality(Function("ResourceCost", [m2], sort=REAL), R_ZERO),
        Equality(Function("ResourceCost", [Function("Seq", [m1, m2])], sort=REAL), Function("ResourceCost", [m1], sort=REAL))
    )))
    
    # Lemma 4: Decomposition of parallel cost under zero dependency
    # Forall M1, M2. Dep(M1, M2) = DEP_ZERO -> ResourceCost(Par_Dyn(M1, M2)) = Comp(Par_Dyn(M1, M2))
    engine.lemmas.append(Forall([m1, m2], Implies(
        Equality(Function("Dep", [m1, m2], sort=REAL), DEP_ZERO),
        Equality(Function("ResourceCost", [Function("Par_Dyn", [m1, m2])], sort=REAL), Function("Comp", [Function("Par_Dyn", [m1, m2])], sort=REAL))
    )))
    
    print(f"[Marathon] Warm started with {len(engine.lemmas)} learned lemmas.")

    # 4. Disable Ceilings & Enable Marathon Liveness
    engine.equilibrium_enabled = False
    engine.marathon_mode = True
    # Boost ATP baseline
    engine._atp_steps_offset = 1000 
    
    # 5. Launch Infinite Loop with Sidecar Observer
    try:
        # Custom cycle callback for sidecar monitoring
        def sidecar_callback(session):
            import json
            status = {
                "cycle": session.cycle,
                "lemmas_count": len(session.theorems),
                "counter_axioms_count": len(session.counter_axioms),
                "atp_offset": engine._atp_steps_offset,
                "saturator_clauses": engine.saturator.max_clauses if hasattr(engine, "saturator") else 0,
                "timestamp": time.time(),
                "last_proved": [str(t.formula) for t in session.theorems[-3:]] if session.theorems else []
            }
            with open("marathon_status.json", "w") as f:
                json.dump(status, f, indent=2)
            print(f"[Sidecar] Status synced to marathon_status.json")

        # Run for 1000 cycles
        session = engine.discover_and_verify_conjectures(
            max_cycles=1000,
            verbose=True,
            cycle_callback=sidecar_callback
        )
        engine.report(session)
    except KeyboardInterrupt:
        print("\n[Marathon] Interrupted by user. Finalizing audit trail...")
    except Exception as e:
        print(f"\n[Marathon] Fatal Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_marathon()
