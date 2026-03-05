"""
prover/lean_exporter.py

Translates CoAI Operandics Formulas into Lean 4 theorem stubs.
Bridges symbolic discovery to formal verification.
"""

from typing import List, Dict, Any
import core.logic as cl
from pathlib import Path

def to_lean_symbol(sym: str) -> str:
    """Map symbolic operands to Lean 4 / Mathlib-like syntax."""
    mapping = {
        "add": "+",
        "minus": "-",
        "multiply": "*",
        "Seq": ">>",  # Custom operandic composition
        "Par_Dyn": "||",
        "Equality": "=",
        "LessEq": "<=",
        "R_ZERO": "0",
        "R_ONE": "1",
        "R_PENALTY": "r_penalty",
        "ID_M": "id_m",
        "P_TRUE": "p_true",
    }
    return mapping.get(sym, sym)

def formula_to_lean(phi: cl.Formula) -> str:
    """Recursively convert a Formula to Lean 4 string."""
    if isinstance(phi, cl.Variable):
        return phi.name
    
    if isinstance(phi, cl.Constant):
        return to_lean_symbol(phi.name)
    
    if isinstance(phi, cl.Function):
        sym = to_lean_symbol(phi.symbol)
        args = [formula_to_lean(a) for a in phi.args]
        
        # Infix operators for readability
        if sym in {"+", "-", "*", "=", "<=", ">>", "||"}:
            if len(args) == 2:
                return f"({args[0]} {sym} {args[1]})"
        
        return f"({sym} {' '.join(args)})"
    
    if isinstance(phi, cl.Equality):
        return f"({formula_to_lean(phi.left)} = {formula_to_lean(phi.right)})"
    
    if isinstance(phi, cl.LessEq):
        return f"({formula_to_lean(phi.left)} <= {formula_to_lean(phi.right)})"
    
    if isinstance(phi, cl.Forall):
        return f"∀ {phi.variable.name}, {formula_to_lean(phi.body)}"
    
    if isinstance(phi, cl.Implies):
        return f"({formula_to_lean(phi.left)} -> {formula_to_lean(phi.right)})"
    
    if isinstance(phi, cl.Not):
        return f"¬({formula_to_lean(phi.formula)})"
    
    return str(phi)

def export_theorem(thm: Any, name_prefix: str = "thm") -> str:
    """
    Export a DiscoveredTheorem as a Lean 4 theorem stub.
    thm: DiscoveredTheorem instance
    """
    # Create a unique name from hash or interestingness
    safe_name = f"{name_prefix}_{abs(hash(str(thm.formula))) % 10000}"
    
    lean_body = formula_to_lean(thm.formula)
    
    # Add metadata as comments
    header = (
        f"-- Interestingness: {thm.interestingness:.4f}\n"
        f"-- Tags: {', '.join(thm.tags)}\n"
        f"-- Cycle: {thm.cycle}\n"
    )
    
    return f"{header}theorem {safe_name} : {lean_body} := by\n  sorry\n"

def export_bundle(theorems: List[Any], bundle_name: str) -> str:
    """Export a list of theorems as a complete Lean 4 file."""
    lines = [
        f"-- CoAI Operandics Discovery: {bundle_name}",
        "import CoAI.Operandics.Core",
        "import CoAI.Operandics.Risk",
        "",
        "open Operandics",
        "",
    ]
    for i, thm in enumerate(theorems):
        lines.append(export_theorem(thm, name_prefix=f"discovery_{i}"))
        lines.append("")
        
    return "\n".join(lines)

def batch_export_by_stage(stages: Dict[int, Any], output_dir: str):
    """
    Exports theorems grouped by stage into Lean files.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    for sid, stage in stages.items():
        if stage.theorems:
            content = export_bundle(stage.theorems, f"Stage_{sid}_{stage.name}")
            file_name = f"Stage_{sid}.lean"
            (out_path / file_name).write_text(content, encoding="utf-8")
            
    print(f"[LEAN EXPORTER] Batch export complete to: {output_dir}")
