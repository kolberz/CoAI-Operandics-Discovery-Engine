#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

TRANCHE_TESTS = (
    "discovery/tests/test_tranche6_integration.py",
    "discovery/tests/test_tranche7_integration.py",
    "discovery/tests/test_tranche8_integration.py",
)

PROFILES = (
    ("baseline", 128, 10),
    ("exploratory", 256, 16),
)

DISCOVERY_FIELDS = (
    "discoveries",
    "proved_theorems",
    "theorems",
    "results",
    "conjectures",
)

HISTORY_FIELDS = (
    "history",
    "_history",
    "novelty_history",
    "qed_history",
    "persistent_history",
)


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if hasattr(value, "__dict__"):
        return {
            str(k): to_jsonable(v)
            for k, v in vars(value).items()
            if not str(k).startswith("__")
        }
    return repr(value)


def extract_discovery_field(session: Any) -> tuple[str | None, Any]:
    for name in DISCOVERY_FIELDS:
        value = getattr(session, name, None)
        if value not in (None, [], {}, ()):
            return name, value
    return None, None


def collection_size(value: Any) -> int | None:
    try:
        return len(value)  # type: ignore[arg-type]
    except Exception:
        return None


def capture_report(engine: Any, session: Any) -> str:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            engine.report(session)
    except Exception as exc:
        return f"<engine.report failed: {exc!r}>"
    return buf.getvalue()


def clear_known_history(engine: Any) -> None:
    targets = [
        engine,
        getattr(engine, "grammar", None),
        getattr(engine, "synthesizer", None),
        getattr(engine, "mcts", None),
    ]
    for target in targets:
        if target is None:
            continue
        for name in HISTORY_FIELDS:
            value = getattr(target, name, None)
            if isinstance(value, dict):
                value.clear()


def run_pytest(test_path: str) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test_path],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "path": test_path,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "elapsed_s": round(time.time() - started, 3),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_profile(name: str, mcts_iters: int, max_cycles: int, out_dir: Path) -> dict[str, Any]:
    os.environ["COAI_MCTS_ITERS"] = str(mcts_iters)

    from discovery.engine import DiscoveryEngine

    started = time.time()
    engine = DiscoveryEngine()
    session = engine.discover_and_verify_conjectures(max_cycles=max_cycles)
    report = capture_report(engine, session)

    field_name, field_value = extract_discovery_field(session)
    stats = getattr(session, "stats", None)

    artifact = {
        "profile": {
            "name": name,
            "mcts_iters": mcts_iters,
            "max_cycles": max_cycles,
        },
        "summary": {
            "elapsed_s": round(time.time() - started, 3),
            "discovery_field": field_name,
            "discovery_count": collection_size(field_value),
            "redundant_skipped": stats.get("redundant_skipped") if isinstance(stats, dict) else None,
        },
        "stats": to_jsonable(stats),
        "discoveries": to_jsonable(field_value),
        "report": report,
        "session": to_jsonable(session),
    }

    out_path = out_dir / f"{name}.json"
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")

    clear_known_history(engine)
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrated discovery runner for CoAI.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip tranche integration tests.")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Run discovery even when tranche tests fail.",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/discovery",
        help="Directory for JSON artifacts.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    test_results: list[dict[str, Any]] = []
    if not args.skip_tests:
        for test_path in TRANCHE_TESTS:
            if not os.path.exists(test_path):
                print(f"Skipping {test_path} (not found)")
                continue
            result = run_pytest(test_path)
            test_results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            print(f"[{status}] {test_path} ({result['elapsed_s']}s)")
        if test_results:
            (out_dir / "calibration.json").write_text(
                json.dumps(test_results, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        failed = [r for r in test_results if not r["passed"]]
        if failed and not args.allow_dirty:
            print("Calibration failed. Discovery run aborted.")
            return 1

    for name, mcts_iters, max_cycles in PROFILES:
        artifact = run_profile(name, mcts_iters, max_cycles, out_dir)
        summary = artifact["summary"]
        print(
            f"[DISCOVERY] {name}: "
            f"field={summary['discovery_field']}, "
            f"count={summary['discovery_count']}, "
            f"redundant_skipped={summary['redundant_skipped']}, "
            f"elapsed={summary['elapsed_s']}s"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
