import json
from rupture_wrapper import run_rupture
from invariant_wrapper import run_invariants
from fusion_config import (
    RUPTURE_WEIGHT, INVARIANT_WEIGHT,
    RUPTURE_PEAK_MULTIPLIER, RUPTURE_COUNT_MULTIPLIER, RUPTURE_MAX,
    INV_SCORE_B1_ZERO, INV_SCORE_B0_SPLIT,
    INV_SCORE_WARNING, INV_SCORE_CRITICAL, INV_MAX,
    THRESHOLD_CRITICAL, THRESHOLD_HIGH, THRESHOLD_MEDIUM,
)

def score_rupture(r):
    raw = r.get("raw", [])
    if not raw:
        return 0.0

    peak = max(event.get("peak_rho", 0.0) for event in raw)
    count = len(raw)

    score = min(
        (RUPTURE_PEAK_MULTIPLIER * peak) + (RUPTURE_COUNT_MULTIPLIER * count),
        RUPTURE_MAX,
    )
    return score

def score_invariants(inv):
    stages = inv.get("stages", [])
    advisories = inv.get("advisories", [])

    score = 0.0

    for stage in stages:
        if stage["b1"] == 0:
            score += INV_SCORE_B1_ZERO
        if stage["b0"] > 1:
            score += INV_SCORE_B0_SPLIT

    for adv in advisories:
        if adv["severity"] == "WARNING":
            score += INV_SCORE_WARNING
        elif adv["severity"] == "CRITICAL":
            score += INV_SCORE_CRITICAL

    return min(score, INV_MAX)

def compute_risk():
    rupture = run_rupture()
    invariants = run_invariants()

    r = score_rupture(rupture)
    i = score_invariants(invariants)

    score = RUPTURE_WEIGHT * r + INVARIANT_WEIGHT * i

    if score >= THRESHOLD_CRITICAL:
        level = "CRITICAL"
    elif score >= THRESHOLD_HIGH:
        level = "HIGH"
    elif score >= THRESHOLD_MEDIUM:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "risk_score": round(score, 3),
        "risk_level": level,
        "signals": {
            "rupture_score": round(r, 3),
            "invariant_score": round(i, 3),
            "rupture": rupture,
            "invariants": invariants,
        }
    }

if __name__ == "__main__":
    import os
    result = compute_risk()

    print(json.dumps(result, indent=2))

    os.makedirs("output", exist_ok=True)
    out_path = "output/beep_output.json"
    if os.path.exists(out_path):
        os.chmod(out_path, 0o644)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
