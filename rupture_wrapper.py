import json
import os
import subprocess
from pathlib import Path

RUPTURE_DIR = Path(os.environ.get(
    "BEEP_RUPTURE_DIR",
    str(Path.home() / "Desktop/DataDrive/rust_project/rupture-engine"),
))
OUTPUT_DIR  = RUPTURE_DIR / "output" / "demo"
CONFIG      = RUPTURE_DIR / "configs" / "stress_demo.toml"
DATA        = RUPTURE_DIR / "data" / "fixtures" / "scenA_base_ohlcv.csv"
META        = RUPTURE_DIR / "data" / "fixtures" / "scenA_base_meta.json"

def run_rupture():
    exe = RUPTURE_DIR / "target" / "debug" / "rupture-engine"

    if not exe.exists():
        subprocess.run(
            ["cargo", "build"],
            cwd=RUPTURE_DIR,
            check=True,
        )

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

    # Only count CONFIRMED events (those with confirmed_timestamp set)
    raw_list = events if isinstance(events, list) else events.get("events", [])
    confirmed = [ev for ev in raw_list if ev.get("confirmed_timestamp") is not None]

    # Load scenario metadata (phase boundaries for HTML report)
    meta = {}
    if META.exists():
        with open(META) as f:
            meta = json.load(f)

    return {
        "engine":           "rupture-engine",
        "event_count":      len(confirmed),
        "raw":              confirmed,
        "scenario_meta":    meta,
    }

if __name__ == "__main__":
    print(json.dumps(run_rupture(), indent=2))
