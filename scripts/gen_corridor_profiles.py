import json
from pathlib import Path

INP = Path("docs/corridor_calibration_summary.json")
OUT = Path("docs/corridor_profiles.json")

def getp(summary, key, p, default=None):
    d = summary.get(key, {})
    v = d.get(str(p), d.get(p, default))
    return default if v is None else float(v)

def main():
    s = json.loads(INP.read_text(encoding="utf-8"))

    profiles = {}

    def make(name, eceil_p, nceil_p, afloor_p, dfloor_p, efloor_p, simceil_p):
        profiles[name] = {
            "entropy_ceiling": getp(s, "entropy", eceil_p, 4.0),
            "norm_ceiling": getp(s, "embedding_norm", nceil_p, 12.0),
            "attention_floor": getp(s, "attention_coherence", afloor_p, 0.4),
            "divergence_floor": getp(s, "manifold_divergence", dfloor_p, 0.1),
            "entropy_floor": getp(s, "entropy", efloor_p, 0.3),
            "similarity_ceiling": getp(s, "centroid_similarity", simceil_p, 0.95),
        }

    make("conservative", 90, 90, 20, 10, 10, 90)
    make("balanced",     95, 95, 10,  5,  5, 95)
    make("aggressive",   99, 99,  5,  1,  1, 99)

    OUT.write_text(json.dumps(profiles, indent=2, sort_keys=True), encoding="utf-8")
    print("Wrote", OUT)

if __name__ == "__main__":
    main()
