import sys
import io
from pathlib import Path

# Force UTF-8 for stdout to prevent UnicodeEncodeError on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import core.logic as cl
from discovery.engine import DiscoveredTheorem
import prover.lean_exporter as exporter

def test_lean_export():
    m1 = cl.Variable("M1", cl.MODULE)
    m2 = cl.Variable("M2", cl.MODULE)
    
    # Theorem: Risk(Seq(M1, M2)) = add(Risk(M1), Risk(M2))
    risk_seq = cl.Function("Risk", (cl.Function("Seq", (m1, m2), cl.MODULE),), cl.REAL)
    risk_sum = cl.Function("add", (cl.Function("Risk", (m1,), cl.REAL), cl.Function("Risk", (m2,), cl.REAL)), cl.REAL)
    
    formula = cl.Forall(m1, cl.Forall(m2, cl.Equality(risk_seq, risk_sum)))
    
    thm = DiscoveredTheorem(
        formula=formula,
        interestingness=0.95,
        tags={"algebra", "risk"},
        verification="PROVED",
        cycle=5
    )
    
    lean_code = exporter.export_theorem(thm)
    print("Generated Lean Code:")
    print(lean_code)
    
    assert "M1 >> M2" in lean_code
    # Use hex/unicode comparison to be safe
    assert "\u2200" in lean_code or "forall" in lean_code.lower()
    
    # Check bundle export
    bundle = exporter.export_bundle([thm], "AttentionDiscovery")
    assert "import CoAI.Operandics.Core" in bundle
    print("SUCCESS: Lean export verified.")

if __name__ == "__main__":
    test_lean_export()
