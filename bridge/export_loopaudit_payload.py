#!/usr/bin/env python3
"""
bridge/export_loopaudit_payload.py

Reads beep_pipeline output and emits a canonical LoopAudit bridge payload.

Risk scores, fusion weights, and HTML presentation layers are excluded.
Only structural certificates, regional transitions, and rupture witnesses
are included — these form the trusted boundary for LoopAudit ingestion.

Usage:
    python3 bridge/export_loopaudit_payload.py
    python3 bridge/export_loopaudit_payload.py --input output/beep_output.json
    python3 bridge/export_loopaudit_payload.py --input output/beep_output.json --output output/beep_loopaudit_payload.json
"""

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

STAGE_HEADER_RE = re.compile(r"STAGE\s+(\d+)")
ADVISORY_RE = re.compile(r"\[(WARNING|CRITICAL)\]\s+([A-Z0-9_]+)")


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def prev_weekday(d: date) -> date:
    """Return d minus one day, rolling back over weekends."""
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


# ---------------------------------------------------------------------------
# Region construction
# ---------------------------------------------------------------------------

def build_regions(meta: dict) -> list[dict]:
    """
    Build the ordered list of regional nodes from scenario metadata.

    Four phases are always expected: warmup, phase1, phase2, phase3.
    End timestamps are derived as the last weekday before the next region starts.
    Phase3 end is estimated as start + 28 calendar days (≈ 20 trading days).
    """
    phase_keys = ["warmup", "phase1", "phase2", "phase3"]
    starts = {
        "warmup": meta["warmup_ts"],
        "phase1": meta["phase1_ts"],
        "phase2": meta["phase2_ts"],
        "phase3": meta["phase3_ts"],
    }
    indices = {
        "warmup":  (meta["warmup_start"],  meta["warmup_end"]),
        "phase1":  (meta["phase1_start"],  meta["phase1_end"]),
        "phase2":  (meta["phase2_start"],  meta["phase2_end"]),
        "phase3":  (meta["phase3_start"],  meta["phase3_end"]),
    }

    regions = []
    for i, key in enumerate(phase_keys):
        start_ts = starts[key]
        if i + 1 < len(phase_keys):
            next_start = date.fromisoformat(starts[phase_keys[i + 1]])
            end_ts = str(prev_weekday(next_start))
        else:
            end_ts = str(date.fromisoformat(start_ts) + timedelta(days=28))

        s, e = indices[key]
        regions.append({
            "region_id":    key,
            "start_index":  s,
            "end_index":    e,
            "start_ts":     start_ts,
            "end_ts":       end_ts,
        })
    return regions


# ---------------------------------------------------------------------------
# Per-stage advisory extraction
# ---------------------------------------------------------------------------

def extract_per_stage_advisories(raw_output: str) -> dict[int, list[str]]:
    """
    Re-parse the raw invariant output to associate advisory codes with the
    stage they were emitted under.

    Returns {stage_number (1-indexed): [advisory_code, ...]}.
    """
    per_stage: dict[int, list[str]] = {}
    current_stage: int | None = None

    for line in raw_output.splitlines():
        stage_match = STAGE_HEADER_RE.search(line)
        if stage_match:
            current_stage = int(stage_match.group(1))
            per_stage.setdefault(current_stage, [])
            continue

        if current_stage is not None:
            adv_match = ADVISORY_RE.search(line)
            if adv_match:
                per_stage[current_stage].append(adv_match.group(2))

    return per_stage


# ---------------------------------------------------------------------------
# Structural observations
# ---------------------------------------------------------------------------

def build_structural_observations(
    stages: list[dict],
    per_stage_advisories: dict[int, list[str]],
    regions: list[dict],
) -> list[dict]:
    """
    Map each invariant stage to a structural observation attached to a region.

    Stage i (1-indexed) maps to region i-1 (0-indexed in the regions list).
    If there are more regions than stages (e.g. phase3 has no new invariant
    stage), those trailing regions are left without a structural observation.
    """
    obs = []
    for idx, stage in enumerate(stages):
        region_id = regions[idx]["region_id"]
        advisories = per_stage_advisories.get(idx + 1, [])
        obs.append({
            "region_id":  region_id,
            "system":     stage["system"],
            "b0":         stage["b0"],
            "b1":         stage["b1"],
            "advisories": advisories,
        })
    return obs


# ---------------------------------------------------------------------------
# Rupture observations
# ---------------------------------------------------------------------------

def build_rupture_observations(raw_events: list[dict]) -> list[dict]:
    """
    Map rupture engine events to bridge rupture observations.

    Only fields needed for structural witnessing are retained.
    Confirmation lag, peak heuristics, and threshold parameters
    are excluded from the trusted boundary.
    """
    result = []
    for ev in raw_events:
        result.append({
            "candidate_index": ev["candidate_index"],
            "candidate_ts":    ev["candidate_timestamp"],
            "confirmed_index": ev.get("confirmed_index"),
            "confirmed_ts":    ev.get("confirmed_timestamp"),
            "peak_rho":        ev["peak_rho"],
        })
    return result


# ---------------------------------------------------------------------------
# Derived transitions
# ---------------------------------------------------------------------------

def _compatibility_status(b0_from: int, b1_from: int, b0_to: int, b1_to: int) -> str:
    ring_lost   = b1_from > 0 and b1_to == 0
    partitioned = b0_to > b0_from

    if ring_lost and partitioned:
        return "ring_broken_and_partitioned"
    elif ring_lost:
        return "ring_broken"
    elif partitioned:
        return "partitioned"
    else:
        return "coherent"


def build_derived_transitions(obs: list[dict]) -> list[dict]:
    """
    Compute the declared transition between each consecutive pair of
    structural observations.

    Each transition captures the before/after delta for b0 and b1,
    and a compatibility_status label that LoopAudit uses as the
    transport comparison key.
    """
    transitions = []
    for i in range(len(obs) - 1):
        src = obs[i]
        dst = obs[i + 1]
        status = _compatibility_status(src["b0"], src["b1"], dst["b0"], dst["b1"])
        transitions.append({
            "from_region": src["region_id"],
            "to_region":   dst["region_id"],
            "delta": {
                "b0": [src["b0"], dst["b0"]],
                "b1": [src["b1"], dst["b1"]],
            },
            "compatibility_status": status,
        })
    return transitions


# ---------------------------------------------------------------------------
# Top-level payload builder
# ---------------------------------------------------------------------------

def export_payload(beep_output: dict) -> dict:
    """
    Build the full bridge payload from a beep_pipeline output dict.

    The payload contains only the trusted boundary fields:
      - timeline regions
      - structural observations (b0, b1, advisories per region)
      - rupture observations (candidate/confirmed events as empirical witnesses)
      - derived transitions (transport deltas and compatibility labels)

    Excluded: risk_score, risk_level, fusion weights, HTML, raw_output prose.
    """
    signals   = beep_output["signals"]
    rupture   = signals["rupture"]
    invariants = signals["invariants"]

    meta            = rupture["scenario_meta"]
    regions         = build_regions(meta)
    per_stage_adv   = extract_per_stage_advisories(invariants.get("raw_output", ""))
    structural_obs  = build_structural_observations(invariants["stages"], per_stage_adv, regions)
    rupture_obs     = build_rupture_observations(rupture["raw"])
    transitions     = build_derived_transitions(structural_obs)

    return {
        "schema_version":          "beep.loopaudit.bridge.v1",
        "scenario_id":             meta["name"],
        "timeline": {
            "total_rows": meta["total_rows"],
            "regions":    regions,
        },
        "structural_observations": structural_obs,
        "rupture_observations":    rupture_obs,
        "derived_transitions":     transitions,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export BEEP pipeline output as a LoopAudit bridge payload."
    )
    parser.add_argument(
        "--input",
        default="output/beep_output.json",
        help="Path to beep_output.json (default: output/beep_output.json)",
    )
    parser.add_argument(
        "--output",
        default="output/beep_loopaudit_payload.json",
        help="Destination path for the bridge payload (default: output/beep_loopaudit_payload.json)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        beep_output = json.load(f)

    payload = export_payload(beep_output)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"bridge payload written → {output_path}")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
