import sys
import json
import subprocess
from pathlib import Path
import pytest
import shutil

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT))

def test_missing_theorem_fails(tmp_path):
    # Setup temporary environment
    import add_attention_axioms
    
    # We will temporarily override the BASE_JSON inside the module
    original_base = add_attention_axioms.BASE_JSON
    
    try:
        tmp_base = tmp_path / "attention_axioms.json"
        # Write an invalid rule
        fake_data = {
            "schema_version": 1,
            "bundle": "attention",
            "rules": [
                {
                    "id": "bad_rule",
                    "lean": {
                        "theorem": "StochasticAttention.fake_theorem_does_not_exist"
                    }
                }
            ]
        }
        tmp_base.write_text(json.dumps(fake_data), encoding="utf-8")
        
        # Override the path
        add_attention_axioms.BASE_JSON = tmp_base
        
        # It should raise a SystemExit with the exact message we expect
        with pytest.raises(SystemExit, match=r"Lean theorem not found in manifest output: StochasticAttention.fake_theorem_does_not_exist"):
            add_attention_axioms.main()
            
    finally:
        # Restore the path
        add_attention_axioms.BASE_JSON = original_base
