from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

ALLOWLIST = {"propext", "Classical.choice", "Quot.sound"}

ROOT = Path(__file__).resolve().parent
DISCOVERY_AXIOMS_DIR = ROOT / "discovery" / "axioms"
BASE_JSON = DISCOVERY_AXIOMS_DIR / "attention_axioms.json"
VERIFIED_JSON = DISCOVERY_AXIOMS_DIR / "attention_axioms.verified.json"

COAI_DIR = ROOT / "coai_project_experimental"
LEAN_MANIFEST = COAI_DIR / "CoAI" / "Export" / "Manifest.lean"

BEGIN = re.compile(r"^BEGIN (.+)$")
END = re.compile(r"^END (.+)$")
AXIOMS = re.compile(r"depends on axioms:\s*\[(.*)\]")

LOG_DIR = DISCOVERY_AXIOMS_DIR / "_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LEAN_ERROR_LOG = LOG_DIR / "lean_error.log"

def run_lean_manifest() -> str:
    # Run Lean in the CoAI project directory
    try:
        p = subprocess.run(
            ["lake", "env", "lean", str(LEAN_MANIFEST)],
            cwd=str(COAI_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return p.stdout + "\n" + p.stderr
    except subprocess.CalledProcessError as e:
        LEAN_ERROR_LOG.write_text(
            f"Exit code: {e.returncode}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}", 
            encoding="utf-8"
        )
        print(f"Lean failed with exit code {e.returncode}. See {LEAN_ERROR_LOG} for details.")
        raise

def parse_manifest(output: str) -> dict[str, dict]:
    """
    Returns: theorem_name -> {"type": "...", "axioms": [..]}
    We parse BEGIN/END blocks and grab:
      - first line with `name : <type>`
      - line containing `depends on axioms: [...]`
    """
    lines = output.splitlines()
    i = 0
    info: dict[str, dict] = {}
    while i < len(lines):
        m = BEGIN.match(lines[i].strip())
        if not m:
            i += 1
            continue
        name = m.group(1).strip()
        i += 1
        block = []
        while i < len(lines) and lines[i].strip() != f"END {name}":
            block.append(lines[i])
            i += 1
        if i >= len(lines):
            raise SystemExit(f"Manifest parse error: missing END marker for theorem block '{name}'")

        typ = None
        axioms_list: list[str] = []
        saw_axioms_line = False
        for ln in block:
            s = ln.strip()
            # type line usually prints as: <name> : <type>
            if s.startswith(name) and ":" in s and typ is None:
                typ = s.split(":", 1)[1].strip()
            if "depends on axioms:" in s:
                saw_axioms_line = True
                m2 = AXIOMS.search(s)
                if m2:
                    axioms_list = [a.strip() for a in m2.group(1).split(",") if a.strip()]

        info[name] = {"type": typ, "axioms": axioms_list, "saw_axioms_line": saw_axioms_line}
        i += 1
    return info

def categorize_lean_theorem(theorem_name: str, typ: str | None, axioms: list[str]) -> str:
    """Deterministically categorizes a theorem into a provenance layer."""
    if theorem_name.startswith("Matrix.") or "factorize" in theorem_name or "LinearRouting" in theorem_name:
        return "algebra"
        
    sig = theorem_name + (" " + typ if typ else "")
    
    if any(k in sig for k in ["MeasureTheory", "ProbabilityTheory", "HasSubgaussianMGF", "Martingale", "CoAI.SubGaussian."]):
        return "statistical"
        
    if any(k in sig for k in ["Real.exp", "Real.log", "Trigonometric", "cos", "sin", "FAVOR", "GaussianCharFun"]):
        return "analytic"
        
    if all(a in ALLOWLIST for a in axioms):
        return "foundation"
        
    return "uncategorized"

def main() -> None:
    base = json.loads(BASE_JSON.read_text(encoding="utf-8"))
    manifest_out = run_lean_manifest()
    lean_info = parse_manifest(manifest_out)

    for rule in base["rules"]:
        if "lean" not in rule or "theorem" not in rule["lean"]:
            raise SystemExit(f"Rule missing lean.theorem field: {rule.get('id', '<no id>')}")
        thm = rule["lean"]["theorem"]
        if not isinstance(thm, str) or not thm.strip():
            raise SystemExit(f"Rule has invalid lean.theorem (must be non-empty string): {rule.get('id','<no id>')}")
        if thm not in lean_info:
            raise SystemExit(f"Lean theorem not found in manifest output: {thm}")

        typ = lean_info[thm]["type"]
        axioms = lean_info[thm]["axioms"]
        saw_axioms_line = lean_info[thm]["saw_axioms_line"]

        if typ is None:
            raise SystemExit(f"Manifest missing #check type line for theorem: {thm}")
        if not saw_axioms_line:
            raise SystemExit(f"Manifest missing '#print axioms' output line for theorem: {thm}")

        rule["lean"]["type"] = typ
        rule["lean"]["axioms"] = axioms
        rule["lean"]["category"] = categorize_lean_theorem(thm, typ, axioms)

        bad = [a for a in rule["lean"]["axioms"] if a not in ALLOWLIST]
        if bad:
            raise SystemExit(f"Axiom footprint violates allowlist for {thm}: {bad}")

    VERIFIED_JSON.write_text(json.dumps(base, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote verified bundle: {VERIFIED_JSON}")

if __name__ == "__main__":
    main()
