from __future__ import annotations
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Your project imports (adjust if paths differ)
from grounding.dimensions import DimensionRegistry, DimensionalChecker
from discovery.engine import CoAIOperandicsExplorer

from web.sexpr_parser import parse_axioms_sexpr, ParseError
from web.registry_parse import parse_dim_string, apply_registry_overrides

app = FastAPI(title="CoAI Gate 3 API")

# serve web/
app.mount("/static", StaticFiles(directory="web", html=True), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    with open("web/index.html", "r", encoding="utf-8") as f:
        return f.read()


class Gate3CheckRequest(BaseModel):
    mode: str = "oneoff"  # "oneoff" or "engine"
    axioms_text: str = ""
    const_overrides: Dict[str, str] = {}
    func_overrides: Dict[str, str] = {}
    coverage_sample_n: int = 10


@app.get("/api/gate3/defaults")
def gate3_defaults():
    reg = DimensionRegistry()
    # Convert Dimension objects to strings for JSON
    const_dims = {k: str(v) for k, v in reg.const_dims.items()}
    output_dims = {k: (None if v is None else str(v)) for k, v in reg.output_dims.items()}
    return {"const_dims": const_dims, "output_dims": output_dims}


@app.post("/api/gate3/check")
def gate3_check(req: Gate3CheckRequest):
    # Build registry + apply overrides
    reg = DimensionRegistry()
    apply_registry_overrides(reg, req.const_overrides, req.func_overrides)

    checker = DimensionalChecker(registry=reg)

    # Parse user axioms (S-expr) to AST
    try:
        user_axioms, user_names = parse_axioms_sexpr(req.axioms_text)
    except ParseError as e:
        return {"verdict": "FAIL", "error": f"ParseError: {e}"}

    axioms: List[Any] = []
    names: List[str] = []

    if req.mode == "engine":
        e = CoAIOperandicsExplorer(max_clauses=100, max_depth=3, min_interestingness=0.1)
        axioms.extend(e.axioms)
        names.extend([f"engine_axiom_{i}" for i in range(len(e.axioms))])

    axioms.extend(user_axioms)
    names.extend([f"user_axiom_{i}" for i in range(len(user_axioms))])

    report = checker.check_axiom_set(axioms, names, coverage_sample_n=req.coverage_sample_n)

    # DimError objects might not be JSON-serializable—normalize
    errors = []
    for err in report.errors:
        errors.append({
            "axiom_name": getattr(err, "axiom_name", ""),
            "message": getattr(err, "message", ""),
            "left_dim": str(getattr(err, "left_dim", None)),
            "right_dim": str(getattr(err, "right_dim", None)),
            "path": getattr(err, "path", ""),
        })

    return {
        "verdict": report.verdict,
        "passes_deployment": report.passes_deployment,
        "checked": report.checked,
        "unknown_required": report.unknown_required,
        "unknown_coverage": report.unknown_coverage,
        "coverage_sample": report.coverage_sample,
        "checker_version": getattr(report, "checker_version", None),
        "calibration_markers": getattr(report, "calibration_markers", None),
        "unknown_constants": sorted(list(getattr(report, "unknown_constants", []))),
        "errors": errors,
        "warnings": report.warnings,
    }
