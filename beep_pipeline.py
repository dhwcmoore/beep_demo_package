import json
import os
from rupture_wrapper import run_rupture, CONFIG, DATA, META
from invariant_wrapper import run_invariants
from fusion_config import (
    RUPTURE_WEIGHT,
    INVARIANT_WEIGHT,
    RUPTURE_PEAK_MULTIPLIER,
    RUPTURE_COUNT_MULTIPLIER,
    RUPTURE_MAX,
    INV_SCORE_B1_ZERO,
    INV_SCORE_B0_SPLIT,
    INV_SCORE_WARNING,
    INV_SCORE_CRITICAL,
    INV_MAX,
    THRESHOLD_CRITICAL,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
)


def score_rupture(r: dict) -> dict:
    raw = r.get("raw", [])
    if not raw:
        return {"score": 0.0, "features": {"event_count": 0, "filtered_event_count": 0, "max_peak_rho": 0.0, "phase_threshold": 0}}

    meta = r.get("scenario_meta", {})
    phase2_start = meta.get("phase2_start", 0)

    filtered = [ev for ev in raw if ev.get("candidate_index", -1) >= phase2_start]

    if not filtered:
        return {"score": 0.0, "features": {"event_count": len(raw), "filtered_event_count": 0, "max_peak_rho": 0.0, "phase_threshold": phase2_start}}

    peak = max(event.get("peak_rho", 0.0) for event in filtered)
    count = len(filtered)

    score = min(
        (RUPTURE_PEAK_MULTIPLIER * peak) + (RUPTURE_COUNT_MULTIPLIER * count),
        RUPTURE_MAX,
    )
    return {
        "score": score,
        "features": {
            "event_count": len(raw),
            "filtered_event_count": count,
            "max_peak_rho": peak,
            "phase_threshold": phase2_start
        }
    }


def score_invariants(inv: dict) -> float:
    nominal = inv.get("nominal_betti") or {}
    fault = inv.get("fault_betti") or {}
    advisories = inv.get("advisories", [])

    score = 0.0

    if nominal and fault:
        nominal_b0 = nominal.get("b0", 0)
        nominal_b1 = nominal.get("b1", 0)
        fault_b0 = fault.get("b0", 0)
        fault_b1 = fault.get("b1", 0)

        if fault_b0 > nominal_b0:
            score += INV_SCORE_B0_SPLIT

        if fault_b1 < nominal_b1:
            score += INV_SCORE_B1_ZERO

    for adv in advisories:
        sev = adv.get("severity", "")
        if sev == "WARNING":
            score += INV_SCORE_WARNING
        elif sev == "CRITICAL":
            score += INV_SCORE_CRITICAL

    return min(score, INV_MAX)


def compute_risk() -> dict:
    rupture = run_rupture()
    invariants = run_invariants()

    rupture_result = score_rupture(rupture)
    rupture_score = rupture_result["score"]
    rupture_features = rupture_result["features"]
    invariant_score = score_invariants(invariants)

    score = (RUPTURE_WEIGHT * rupture_score) + (INVARIANT_WEIGHT * invariant_score)

    nominal = invariants.get("nominal_betti") or {}
    fault = invariants.get("fault_betti") or {}

    source = invariants.get("structural_judgement_source")
    version = invariants.get("structural_semantics_version")
    judgement = invariants.get("structural_judgement")

    if source != "ocaml":
        raise RuntimeError(
            f"Structural judgement source mismatch: expected 'ocaml', got '{source}'"
        )
    if version != "v1":
        raise RuntimeError(
            f"Structural semantics version mismatch: expected 'v1', got '{version}'"
        )
    if judgement is None:
        raise RuntimeError("Missing structural_judgement from invariants payload")

    allowed_judgements = {"SJ_NoBreak", "SJ_CycleLoss", "SJ_ConnectivityPartition"}
    if judgement not in allowed_judgements:
        raise RuntimeError(
            f"Unknown structural_judgement '{judgement}'. Expected one of {sorted(allowed_judgements)}"
        )

    structural_break = False
    structural_reason = None

    if judgement == "SJ_ConnectivityPartition":
        structural_break = True
        structural_reason = "connectivity_partition"
    elif judgement == "SJ_CycleLoss":
        structural_break = True
        structural_reason = "cycle_loss"

    if score >= THRESHOLD_CRITICAL:
        level = "CRITICAL"
    elif score >= THRESHOLD_HIGH:
        level = "HIGH"
    elif score >= THRESHOLD_MEDIUM:
        level = "MEDIUM"
    else:
        level = "LOW"

    if structural_break and rupture_score > 0:
        if level == "LOW":
            level = "MEDIUM"
        elif level == "MEDIUM":
            level = "HIGH"
        elif level == "HIGH":
            level = "CRITICAL"

    if rupture_score > 0:
        if judgement == "SJ_ConnectivityPartition" and level != "CRITICAL":
            raise RuntimeError(
                "Risk escalation contract violated: SJ_ConnectivityPartition with rupture must be CRITICAL"
            )
        if judgement == "SJ_CycleLoss" and level not in {"HIGH", "CRITICAL"}:
            raise RuntimeError(
                "Risk escalation contract violated: SJ_CycleLoss with rupture must be HIGH or CRITICAL"
            )

    # Rupture guardrail: escalation-classified ruptures cannot yield LOW
    has_escalation = any(ev.get("classification") == "Escalation" for ev in rupture.get("classified_events", []))
    if has_escalation and level == "LOW":
        raise RuntimeError("Rupture contract violated: Escalation-classified ruptures cannot yield LOW risk level")

    return {
        "risk_score": round(score, 3),
        "risk_level": level,
        "structural_break": structural_break,
        "structural_reason": structural_reason,
        "structural_judgement_source": invariants.get("structural_judgement_source", "ocaml"),
        "structural_semantics_version": "v1",
        "structural_inputs": invariants.get("structural_inputs", {}),
        "rupture_semantics_version": "v1",
        "rupture_contract": "rupture_contract.v",
        "rupture_features": rupture_features,
        "semantic_contracts": {
            "structural_semantics_version": invariants.get("structural_semantics_version", "v1"),
            "structural_judgement_source": invariants.get("structural_judgement_source", "ocaml"),
            "structural_contract": "structural_judgement_contract.v",
            "rupture_contract": "rupture_contract.v",
            "risk_contract": "risk_escalation_contract.v",
            "guardrails_enforced": True,
        },
        "signals": {
            "rupture_score": round(rupture_score, 3),
            "invariant_score": round(invariant_score, 3),
            "rupture": rupture,
            "invariants": invariants,
        },
    }

    return result


if __name__ == "__main__":
    result = compute_risk()

    print(json.dumps(result, indent=2))

    os.makedirs("output", exist_ok=True)
    out_path = "output/beep_output.json"
    if os.path.exists(out_path):
        os.chmod(out_path, 0o644)

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
