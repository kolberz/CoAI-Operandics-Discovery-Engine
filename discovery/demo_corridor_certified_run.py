import os, json, sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from discovery.engine import CoAIOperandicsExplorer

def main():
    os.environ["COAI_CERTIFIED_MODE"] = "1"

    explorer = CoAIOperandicsExplorer(certified_mode=True)
    session = explorer.discover_and_verify_conjectures(
        cumulative=True,
        max_cycles=5,   # Reduced from 10 for faster demo execution, can be increased later
        verbose=True
    )
    explorer.report(session)

    # Persist metadata for later plotting
    os.makedirs("docs", exist_ok=True)
    with open("docs/demo_corridor_metadata.json", "w", encoding="utf-8") as f:
        json.dump(session.metadata, f, indent=2, sort_keys=True)
    print("Wrote docs/demo_corridor_metadata.json")

    # Provenance demo logic
    print("\n--- Provenance Demo ---")
    applied = session.metadata.get("applied_rules_counter", {})
    if applied:
        top_k = sorted(applied.items(), key=lambda x: x[1], reverse=True)[:10]
        print("Top 10 applied rules:")
        for r, c in top_k:
            print(f"  {r}: {c}")
    else:
        print("No rules applied.")

    outcomes = session.metadata.get("corridor_outcomes", [])
    if outcomes:
        print("\nLast Corridor Snapshot:")
        last = outcomes[-1]
        print(f"  Regime: {last.get('regime')}")
        print(f"  Risk: {last.get('risk')}")

if __name__ == "__main__":
    main()
