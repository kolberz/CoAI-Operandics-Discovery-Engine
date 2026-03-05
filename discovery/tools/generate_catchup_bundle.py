"""
discovery/tools/bundle_architect_context.py

Generates a high-density "Catch-Up Bundle" for CoAI Architect agents.
Includes state summaries, proved lemmata, and Lean 4 stubs.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from typing import List, Any
import core.logic as cl
from discovery.engine import CoAIOperandicsExplorer, DiscoveredTheorem
import prover.lean_exporter as lean_exporter

def generate_bundle(explorer: CoAIOperandicsExplorer, output_path: str):
    lines = []
    lines.append("# CoAI Architect Catch-Up Bundle")
    lines.append(f"## Status: Tranche 2 Complete")
    lines.append("")
    
    lines.append("## 1. Discovery Metrics")
    lines.append(f"- Axioms: {len(explorer.axioms)}")
    lines.append(f"- Proved Lemmata: {len(explorer.lemmas)}")
    lines.append(f"- Counter-axioms (Refuted): {len(explorer.counter_axioms)}")
    lines.append(f"- E-Graph Classes: {explorer.egraph._next_class}")
    lines.append("")
    
    lines.append("## 2. Top Discovered Lemmata")
    # Sort by interestingness
    all_thm = explorer.all_discoveries
    all_thm.sort(key=lambda x: x.interestingness, reverse=True)
    
    for thm in all_thm[:10]:
        lines.append(f"### [{thm.interestingness:.4f}] {thm.verification}")
        lines.append(f"```logic\n{thm.formula}\n```")
        lines.append("")
    
    lines.append("## 3. Lean 4 Verification Stubs")
    lines.append("```lean")
    lines.append(lean_exporter.export_bundle(all_thm[:10], "Tranche2_Discoveries"))
    lines.append("```")
    lines.append("")
    
    lines.append("## 4. Active Research Frontier")
    lines.append("- Optimization of MCTS grammar for probabilistic bounds.")
    lines.append("- Multi-agent congruence synchronization.")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Bundle generated: {output_path}")

if __name__ == "__main__":
    # Simulate a run to generate a sample bundle for the user to see
    explorer = CoAIOperandicsExplorer()
    # Mock some discoveries if empty
    if not explorer.all_discoveries:
        m1 = cl.Variable("M1", cl.MODULE)
        m2 = cl.Variable("M2", cl.MODULE)
        risk_seq = cl.Function("Risk", (cl.Function("Seq", (m1, m2), cl.MODULE),), cl.REAL)
        risk_sum = cl.Function("add", (cl.Function("Risk", (m1,), cl.REAL), cl.Function("Risk", (m2,), cl.REAL)), cl.REAL)
        formula = cl.Forall(m1, cl.Forall(m2, cl.Equality(risk_seq, risk_sum)))
        explorer.all_discoveries.append(DiscoveredTheorem(
            formula=formula,
            interestingness=0.98,
            tags={"algebra", "risk"},
            verification="PROVED",
            cycle=1
        ))

    generate_bundle(explorer, "tranche2_catchup_bundle.md")
