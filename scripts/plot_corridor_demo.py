import json
from pathlib import Path
from collections import Counter

import matplotlib.pyplot as plt

INP = Path("docs/demo_corridor_metadata.json")
OUT1 = Path("docs/fig_corridor_metrics.png")
OUT2 = Path("docs/fig_rule_usage_topk.png")
OUT3 = Path("docs/corridor_calibration_summary.json")

def safe_get(d, *ks, default=None):
    cur = d
    for k in ks:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def percentile(vals, p):
    if not vals:
        return None
    xs = sorted(vals)
    i = int(round((p/100) * (len(xs)-1)))
    return xs[max(0, min(len(xs)-1, i))]

def main():
    data = json.loads(INP.read_text(encoding="utf-8"))

    outcomes = data.get("corridor_outcomes", [])
    if not outcomes:
        raise SystemExit("No corridor_outcomes found in demo metadata.")

    cycles = [o.get("cycle", i) for i,o in enumerate(outcomes)]
    risk = [o.get("risk", 0.0) for o in outcomes]
    min_margin = [o.get("min_margin", 0.0) for o in outcomes]
    regime = [o.get("regime", "UNKNOWN") for o in outcomes]

    # Optional LatentState metrics if you logged them
    entropy = [safe_get(o, "state", "entropy") for o in outcomes]
    coherence = [safe_get(o, "state", "attention_coherence") for o in outcomes]
    mag = [safe_get(o, "state", "embedding_norm") for o in outcomes]
    divergence = [safe_get(o, "state", "manifold_divergence") for o in outcomes]
    similarity = [safe_get(o, "state", "centroid_similarity") for o in outcomes]

    def filter_none(xs):
        return [x for x in xs if x is not None]

    # Plot 1: risk + min_margin + (optionally) coherence/entropy/etc
    plt.figure(figsize=(10, 8))

    ax1 = plt.subplot(3,1,1)
    ax1.plot(cycles, risk, marker="o")
    ax1.set_title("Corridor risk accumulation by cycle")
    ax1.set_ylabel("accumulated_risk")

    ax2 = plt.subplot(3,1,2)
    ax2.plot(cycles, min_margin, marker="o")
    ax2.axhline(0.0, linestyle="--", linewidth=1)
    ax2.set_title("Minimum margin by cycle (negative means violation)")
    ax2.set_ylabel("min_margin")

    ax3 = plt.subplot(3,1,3)
    # Show regime as text markers
    ax3.plot(cycles, [0]*len(cycles), linestyle="none")
    for x, r in zip(cycles, regime):
        ax3.text(x, 0, r, rotation=45, ha="right", va="center")
    ax3.set_yticks([])
    ax3.set_title("Regime per cycle")
    ax3.set_xlabel("cycle")

    plt.tight_layout()
    plt.savefig(OUT1, dpi=160)
    print("Wrote", OUT1)

    # Plot 2: top-K applied rules (if present)
    counter = data.get("applied_rules_counter", {})
    if isinstance(counter, dict) and counter:
        c = Counter(counter)
        top = c.most_common(15)
        labels = [k for k,_ in top]
        vals = [v for _,v in top]

        plt.figure(figsize=(10,5))
        plt.bar(labels, vals)
        plt.xticks(rotation=45, ha="right")
        plt.title("Top applied rules (session-wide)")
        plt.ylabel("count")
        plt.tight_layout()
        plt.savefig(OUT2, dpi=160)
        print("Wrote", OUT2)
    else:
        print("No applied_rules_counter found; skipping rule usage plot.")

    # Calibration summary (percentiles for the state metrics if present)
    summary = {
        "entropy": {p: percentile(filter_none(entropy), p) for p in [0, 10, 50, 90, 100]},
        "attention_coherence": {p: percentile(filter_none(coherence), p) for p in [0, 10, 50, 90, 100]},
        "embedding_norm": {p: percentile(filter_none(mag), p) for p in [0, 10, 50, 90, 100]},
        "manifold_divergence": {p: percentile(filter_none(divergence), p) for p in [0, 10, 50, 90, 100]},
        "centroid_similarity": {p: percentile(filter_none(similarity), p) for p in [0, 10, 50, 90, 100]},
        "min_margin": {p: percentile(filter_none(min_margin), p) for p in [0, 10, 50, 90, 100]},
        "risk": {p: percentile(filter_none(risk), p) for p in [0, 10, 50, 90, 100]},
    }
    OUT3.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print("Wrote", OUT3)

if __name__ == "__main__":
    main()
