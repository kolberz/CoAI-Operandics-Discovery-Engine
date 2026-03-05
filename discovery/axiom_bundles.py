from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from discovery.sexpr_parser import parse_formula

def load_axiom_bundle(engine: Any, path: str | Path) -> None:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported schema_version: {data.get('schema_version')}")

    for rule in data["rules"]:
        rule_id = rule["id"]
        var_sorts: Dict[str, str] = rule.get("vars", {})
        sexpr = rule["engine"]["sexpr"]

        formula = parse_formula(sexpr, env={}, var_sorts=var_sorts)
        engine._add_axiom(formula, rule_id)
