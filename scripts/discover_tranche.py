from __future__ import annotations

import os
from pprint import pprint
from typing import Any

from discovery.engine import DiscoveryEngine

# Fresh engine per run helps avoid persistent MCTS history contamination.
PROFILES: tuple[tuple[str, int, int], ...] = (
    ("conservative", 64, 8),
    ("baseline", 128, 12),
    ("exploratory", 256, 16),
)


def extract_payload(session: Any) -> tuple[str | None, Any]:
    """Best-effort extraction across likely session shapes."""
    for name in ("discoveries", "proved_theorems", "theorems", "conjectures", "results"):
        value = getattr(session, name, None)
        if value:
            return name, value
    return None, None


def run_profile(name: str, mcts_iters: int, cycles: int) -> None:
    os.environ["COAI_MCTS_ITERS"] = str(mcts_iters)

    engine = DiscoveryEngine()
    session = engine.discover_and_verify_conjectures(max_cycles=cycles)

    print(f"\n=== {name} | MCTS={mcts_iters} | cycles={cycles} ===")
    engine.report(session)

    stats = getattr(session, "stats", None)
    if stats is not None:
        print("\nstats:")
        pprint(stats)
        if isinstance(stats, dict):
            print(f"redundant_skipped={stats.get('redundant_skipped')}")

    payload_name, payload = extract_payload(session)
    if payload is not None:
        print(f"\n{payload_name}:")
        pprint(payload)
    else:
        print("\nNo standard discovery field found; raw session:")
        pprint(vars(session) if hasattr(session, "__dict__") else repr(session))


def main() -> None:
    for profile in PROFILES:
        try:
            run_profile(*profile)
        except Exception as exc:
            print(f"\nprofile failed: {profile[0]} -> {exc!r}")


if __name__ == "__main__":
    main()
