import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RUPTURE_DIR = Path(
    os.environ.get("BEEP_RUPTURE_DIR", str(ROOT / "rupture_engine"))
)

OUTPUT_DIR = Path(
    os.environ.get("BEEP_RUPTURE_OUTPUT_DIR", str(ROOT / "output"))
)

CONFIG = Path(
    os.environ.get("BEEP_RUPTURE_CONFIG", str(ROOT / "docs" / "archive" / "demo_v2_frozen" / "stress_demo.toml"))
)

DATA = Path(
    os.environ.get("BEEP_RUPTURE_DATA", str(ROOT / "docs" / "archive" / "demo_v2_frozen" / "scenA_base_ohlcv.csv"))
)

META = Path(
    os.environ.get("BEEP_RUPTURE_META", str(ROOT / "docs" / "archive" / "demo_v2_frozen" / "scenA_base_meta.json"))
)


def classify_events(events, meta):
    phase2 = meta.get("phase2_start", 0)
    phase3 = meta.get("phase3_start", 10**9)

    out = []
    for i, ev in enumerate(events):
        idx = ev.get("candidate_index", -1)

        if i == 0 and idx < phase2:
            label = "Early Signal"
        elif idx >= phase3:
            label = "Escalation"
        elif idx >= phase2:
            label = "Primary Rupture"
        else:
            label = "Precursor"

        ev2 = dict(ev)
        ev2["classification"] = label
        out.append(ev2)

    return out


def run_rupture():
    exe = RUPTURE_DIR / "target" / "debug" / "rupture-engine"

    if not exe.exists():
        subprocess.run(
            ["cargo", "build"],
            cwd=RUPTURE_DIR,
            check=True,
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            str(exe),
            "--input", str(DATA),
            "--config", str(CONFIG),
            "--output-dir", str(OUTPUT_DIR),
        ],
        cwd=RUPTURE_DIR,
        check=True,
    )

    events_file = OUTPUT_DIR / "rupture_events.json"
    if not events_file.exists():
        raise FileNotFoundError(f"Missing rupture output: {events_file}")

    with open(events_file, "r", encoding="utf-8") as f:
        events = json.load(f)

    raw_list = events if isinstance(events, list) else events.get("events", [])
    confirmed = [ev for ev in raw_list if ev.get("confirmed_timestamp") is not None]

    detection_start = None
    config_file = OUTPUT_DIR / "config_used.json"
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            detection_start = cfg.get("detection_start_index")

    meta = {}
    if META.exists():
        with open(META, "r", encoding="utf-8") as f:
            meta = json.load(f)

    phase2_start = meta.get("phase2_start", 0)
    filtered_confirmed = [ev for ev in confirmed if ev.get("candidate_index", -1) >= phase2_start]

    classified = classify_events(filtered_confirmed, meta)

    return {
        "engine": "rupture-engine",
        "event_count": len(filtered_confirmed),
        "raw": filtered_confirmed,
        "classified_events": classified,
        "scenario_meta": meta,
        "detection_start_index": detection_start,
        "warmup_mode": "adaptive_with_fallback",
    }


if __name__ == "__main__":
    print(json.dumps(run_rupture(), indent=2))
