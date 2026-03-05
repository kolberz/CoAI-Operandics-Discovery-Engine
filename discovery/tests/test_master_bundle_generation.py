"""
discovery/tests/test_master_bundle_generation.py

Verifies the master bundle synthesis in MasterStageMonitor.
"""

import unittest
import sys
import os
import json
from pathlib import Path

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from discovery.sync.stage_monitor import MasterStageMonitor
from discovery.engine import DiscoveredTheorem
from core.logic import Constant, Equality

class TestMasterBundleGeneration(unittest.TestCase):
    def test_bundle_synthesis(self):
        monitor = MasterStageMonitor()
        
        # Add some mocked theorems to different stages
        thm1 = DiscoveredTheorem(
            formula=Equality(Constant("A"), Constant("A")),
            interestingness=0.95,
            tags={"stage_13", "structural"},
            verification="PROVED"
        )
        
        thm2 = DiscoveredTheorem(
            formula=Equality(Constant("B"), Constant("B")),
            interestingness=0.85,
            tags={"stage_14", "algebra"},
            verification="PROVED"
        )
        
        monitor.record_progress([thm1, thm2])
        
        output_path = "discovery/tests/temp_master_bundle.json"
        monitor.export_master_bundle(output_path)
        
        # Verify file exists and content is correct
        self.assertTrue(os.path.exists(output_path))
        
        with open(output_path, "r", encoding="utf-8") as f:
            bundle = json.load(f)
            
        self.assertEqual(bundle["schema_version"], "4.0.0")
        self.assertEqual(len(bundle["stages"]), 14) # 1-12 complete + 13 + 14
        
        # Check stage 13
        stage13 = next(s for s in bundle["stages"] if s["id"] == 13)
        self.assertEqual(len(stage13["theorems"]), 1)
        self.assertEqual(stage13["theorems"][0]["formula"], "A = A")
        
        print("SUCCESS: Master bundle synthesized and verified.")
        
        # Cleanup
        # os.remove(output_path)

if __name__ == "__main__":
    unittest.main()
