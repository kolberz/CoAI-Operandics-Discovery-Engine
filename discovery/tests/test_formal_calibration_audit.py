"""
discovery/tests/test_formal_calibration_audit.py

Verifies the end-to-end formal calibration and reach audit pipeline.
"""

import unittest
import sys
import os
import shutil
from pathlib import Path

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from discovery.sync.stage_monitor import MasterStageMonitor
from discovery.engine import DiscoveredTheorem
from core.logic import Constant, Equality
from prover.lean_exporter import batch_export_by_stage
from discovery.tools.reach_audit import ReachAudit

class TestFormalCalibrationAudit(unittest.TestCase):
    def test_full_71_stage_audit(self):
        monitor = MasterStageMonitor()
        
        # Simulate theories for ALL 71 stages
        all_theorems = []
        for i in range(1, 72):
            thm = DiscoveredTheorem(
                formula=Equality(Constant(f"V_{i}"), Constant(f"V_{i}")),
                interestingness=0.9,
                tags={f"stage_{i}"},
                verification="PROVED",
                cycle=1
            )
            all_theorems.append(thm)
            
        monitor.record_progress(all_theorems)
        
        # Paths
        bundle_path = "discovery/tests/full_reach_bundle.json"
        lean_dir = "discovery/tests/lean_audit_export"
        
        if os.path.exists(lean_dir):
            shutil.rmtree(lean_dir)
            
        # 1. Export Bundle
        monitor.export_master_bundle(bundle_path)
        
        # 2. Batch Export to Lean
        batch_export_by_stage(monitor.stages, lean_dir)
        
        # 3. Run Audit
        audit = ReachAudit(bundle_path, lean_dir)
        results = audit.run_audit()
        
        audit.print_report(results)
        
        # Assertions
        self.assertTrue(results["success"])
        self.assertEqual(len(results["covered_stages"]), 71)
        self.assertEqual(results["lean_file_count"], 71)
        
        print("SUCCESS: 71-Stage Reach Audit verified.")

if __name__ == "__main__":
    unittest.main()
