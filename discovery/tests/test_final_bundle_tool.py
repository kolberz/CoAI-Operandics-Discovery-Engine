"""
discovery/tests/test_final_bundle_tool.py

Fast smoke test for the generate_reach_bundle.py tool.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import shutil
from pathlib import Path

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from discovery.tools.generate_reach_bundle import main
from discovery.engine import DiscoveredTheorem, DiscoverySession
from core.logic import Constant, Equality

class TestFinalBundleTool(unittest.TestCase):
    @patch('discovery.orchestral_mesh.GovernedOperandicsExplorer.governed_discovery_cycle')
    def test_tool_execution(self, mock_cycle):
        # Mock discovery to reach stage 14 in 2 cycles
        thm1 = DiscoveredTheorem(
            formula=Equality(Constant("A"), Constant("A")),
            interestingness=0.9,
            tags={"stage_13"},
            verification="PROVED"
        )
        thm2 = DiscoveredTheorem(
            formula=Equality(Constant("B"), Constant("B")),
            interestingness=0.9,
            tags={"stage_14"},
            verification="PROVED"
        )
        
        mock_cycle.side_effect = [
            DiscoverySession(theorems=[thm1]),
            DiscoverySession(theorems=[thm2]),
            DiscoverySession(theorems=[]),
            DiscoverySession(theorems=[])
        ]
        
        out_dir = "discovery/tests/fast_smoke_bundle"
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
            
        sys.argv = [
            "generate_reach_bundle.py",
            "--target", "14",
            "--agents", "1",
            "--max-cycles", "5",
            "--out-dir", out_dir
        ]
        
        main()
        
        # Verify files
        self.assertTrue(os.path.exists(os.path.join(out_dir, "verified_master_bundle.json")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "certificates/Stage_13.lean")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "certificates/Stage_14.lean")))
        
        print("SUCCESS: Fast smoke test for generate_reach_bundle.py complete.")

if __name__ == "__main__":
    unittest.main()
