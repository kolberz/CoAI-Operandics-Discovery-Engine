"""
discovery/tests/test_marathon_reach.py

Verifies the Discovery Marathon functionality in OperandicMesh.
Simulates architectural stage progression.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Ensure we can import from core and other local modules
sys.path.append(os.getcwd())

from discovery.orchestral_mesh import OperandicMesh, MeshConfig
from discovery.engine import DiscoveredTheorem, DiscoverySession
from core.logic import Constant, Equality

class TestMarathonReach(unittest.TestCase):
    def test_reach_progression(self):
        config = MeshConfig(num_agents=1, max_cycles=1)
        mesh = OperandicMesh(config)
        
        # Mock the agent's cycle to return theorems with specific stage tags
        # Cycle 0 will prove stage 13
        # Cycle 1 will prove stage 14
        
        mock_theorems_c0 = [
            DiscoveredTheorem(
                formula=Equality(Constant("A"), Constant("A")),
                interestingness=0.9,
                tags={"stage_13"},
                verification="PROVED"
            )
        ]
        
        mock_theorems_c1 = [
            DiscoveredTheorem(
                formula=Equality(Constant("B"), Constant("B")),
                interestingness=0.9,
                tags={"stage_14"},
                verification="PROVED"
            )
        ]
        
        agent = mesh.agents[0]
        agent.governed_discovery_cycle = MagicMock()
        agent.governed_discovery_cycle.side_effect = [
            DiscoverySession(theorems=mock_theorems_c0),
            DiscoverySession(theorems=mock_theorems_c1)
        ]
        
        # Run until stage 14
        mesh.run_until_reach(target_stage=14, max_global_cycles=5)
        
        summary = mesh.monitor.get_summary()
        self.assertEqual(summary["current_max_stage"], 14)
        self.assertTrue(13 in summary["stage_map"]["completed"])
        self.assertTrue(14 in summary["stage_map"]["completed"])
        print("SUCCESS: Marathon reached target stage via simulated discoveries.")

if __name__ == "__main__":
    unittest.main()
