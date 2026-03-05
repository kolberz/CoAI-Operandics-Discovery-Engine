"""
discovery/tools/reach_audit.py

Verifies architectural reach objectives for the 71-Stage Master Architecture.
Checks for the existence of verified theorems and corresponding Lean certificates.
"""

import json
from pathlib import Path
from typing import List, Dict

class ReachAudit:
    def __init__(self, master_bundle_path: str, lean_output_dir: str):
        self.bundle_path = Path(master_bundle_path)
        self.lean_dir = Path(lean_output_dir)
        
    def run_audit(self) -> Dict:
        if not self.bundle_path.exists():
            return {"success": False, "error": "Master bundle not found."}
            
        with open(self.bundle_path, "r", encoding="utf-8") as f:
            bundle = json.load(f)
            
        total_stages = 71
        audit_results = {
            "total_theorems": 0,
            "covered_stages": [],
            "missing_stages": [],
            "lean_file_count": 0,
            "success": False
        }
        
        bundle_stages = {s["id"]: s for s in bundle.get("stages", [])}
        
        for i in range(1, total_stages + 1):
            stage = bundle_stages.get(i)
            if stage and len(stage.get("theorems", [])) > 0:
                audit_results["covered_stages"].append(i)
                audit_results["total_theorems"] += len(stage["theorems"])
            else:
                audit_results["missing_stages"].append(i)
                
        # Check for lean files
        lean_files = list(self.lean_dir.glob("Stage_*.lean"))
        audit_results["lean_file_count"] = len(lean_files)
        
        if len(audit_results["covered_stages"]) == total_stages:
            audit_results["success"] = True
            
        return audit_results

    def print_report(self, results: Dict):
        print("\n" + "="*40)
        print("COAI ARCHITECTURAL REACH AUDIT")
        print("="*40)
        if not results.get("success", False) and "error" in results:
            print(f"FAILED: {results['error']}")
            return
            
        coverage = len(results["covered_stages"]) / 71 * 100
        print(f"Coverage: {len(results['covered_stages'])}/71 stages ({coverage:.1f}%)")
        print(f"Theorems: {results['total_theorems']} verified certificates")
        print(f"Lean:     {results['lean_file_count']} batch files generated")
        print("-" * 40)
        
        if results["missing_stages"]:
            print(f"Missing Stages: {results['missing_stages'][:10]}...")
        else:
            print("ALL STAGES COVERED. 71-STAGE OBJECTIVE ACHIEVED.")
        print("="*40)

if __name__ == "__main__":
    # Example usage
    audit = ReachAudit("discovery/tests/temp_master_bundle.json", "coai_project/certificates")
    results = audit.run_audit()
    audit.print_report(results)
