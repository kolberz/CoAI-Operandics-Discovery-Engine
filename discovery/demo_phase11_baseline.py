import os
import json
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from discovery.engine import CoAIOperandicsExplorer

def main():
    # Force unbuffered output for background logging
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
    
    print("=== CoAI Phase 11 Baseline: 30-Cycle Discovery (Balanced Profile) ===", flush=True)
    
    os.environ["COAI_CERTIFIED_MODE"] = "1"
    
    explorer = CoAIOperandicsExplorer(certified_mode=True)
    
    start_time = time.time()
    
    # Run a 30-cycle discovery with the balanced corridor profile
    session = explorer.discover_and_verify_conjectures(
        cumulative=True,
        max_cycles=30,
        verbose=True,
        corridor_profile="balanced"
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\nBaseline run completed in {duration:.2f} seconds.")
    
    explorer.report(session)
    
    # Prepare results for saving
    results = {
        "duration_seconds": duration,
        "total_cycles": session.stats.get("cycles", 0),
        "theorems_proved": session.stats.get("total_discoveries", 0),
        "redundant_skipped": session.stats.get("redundant_skipped", 0),
        "corridor_outcomes": session.metadata.get("corridor_outcomes", []),
        "applied_rules": session.metadata.get("applied_rules_counter", {})
    }
    
    # Save results
    os.makedirs("docs", exist_ok=True)
    out_path = Path("docs/phase11_baseline_results.json")
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    
    print(f"\nResults saved to {out_path}")

if __name__ == "__main__":
    main()
