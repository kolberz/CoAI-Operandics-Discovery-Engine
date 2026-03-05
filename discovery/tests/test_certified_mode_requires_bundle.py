import os
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

# Fix sys.path to run tests directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from discovery.engine import CoAIOperandicsExplorer

class TestCertifiedModeRequiresBundle(unittest.TestCase):
    def test_missing_bundle_raises_error(self):
        with patch('discovery.engine.Path.exists') as mock_exists:
            mock_exists.return_value = False
            
            os.environ["COAI_CERTIFIED_MODE"] = "1"
            
            with self.assertRaises(RuntimeError) as context:
                explorer = CoAIOperandicsExplorer(certified_mode=True)
            
            self.assertIn("certified mode enabled but bundle missing", str(context.exception).lower())
            
if __name__ == '__main__':
    unittest.main()
