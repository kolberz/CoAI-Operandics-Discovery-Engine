"""
discovery/tools/generate_reach_bundle.py

Main entry point for the CoAI Operandics Architect 4.0 Reach Bundle.
Executes an autonomous discovery marathon across 71 stages and synthesizes all final audit artifacts.
"""

import sys
import os
import time
import argparse
from pathlib import Path

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from discovery.orchestral_mesh import OperandicMesh, MeshConfig
from prover.lean_exporter import batch_export_by_stage
from discovery.tools.reach_audit import ReachAudit

def main():
    parser = argparse.ArgumentParser(description="Generate Architect 4.0 Reach Bundle")
    parser.add_argument("--target", type=int, default=71, help="Target architectural stage")
    parser.add_argument("--agents", type=int, default=4, help="Initial number of agents")
    parser.add_argument("--max-cycles", type=int, default=100, help="Max marathon cycles")
    parser.add_argument("--out-dir", type=str, default="artifacts/architect_4.0_reach", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    bundle_path = out_dir / "verified_master_bundle.json"
    lean_dir = out_dir / "certificates"

    print(f"\n[ARCHITECT 4.0] Initializing Discovery Marathon...")
    print(f"  Target Stage: {args.target}")
    print(f"  Agents:       {args.agents}")
    print(f"  Max Cycles:   {args.max_cycles}")
    print(f"  Output:       {args.out_dir}\n")

    config = MeshConfig(num_agents=args.agents, max_cycles=1)
    mesh = OperandicMesh(config)

    # 1. Execute Marathon
    start_time = time.time()
    mesh.run_until_reach(target_stage=args.target, max_global_cycles=args.max_cycles)
    duration = time.time() - start_time

    # 2. Export Master Bundle
    mesh.monitor.export_master_bundle(str(bundle_path))

    # 3. Batch Export Lean Certificates
    batch_export_by_stage(mesh.monitor.stages, str(lean_dir))

    # 4. Final Final Reach Audit
    audit = ReachAudit(str(bundle_path), str(lean_dir))
    results = audit.run_audit()
    audit.print_report(results)

    print(f"\n[ARCHITECT 4.0] Bundle generation complete in {duration:.1f}s.")
    if results["success"]:
        print("STATUS: SUCCESS - MISSION OBJECTIVE ACHIEVED.")
    else:
        print("STATUS: PARTIAL - REACH OBJECTIVE NOT MET.")

if __name__ == "__main__":
    main()
