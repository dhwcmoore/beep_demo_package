import json
import os
import re
import subprocess
from pathlib import Path

INV_PY = Path(os.environ.get(
    "BEEP_INVARIANT_DIR",
    str(Path.home() / "noindex/BEEP_BEFORE_BANG_MASTER/layers/invariants/boundary_Invarient/boundary-logic-pipeline-main/python"),
))

BETTI_RE = re.compile(r"Betti\s*:\s*\[(\d+),\s*(\d+)\]")
SYSTEM_RE = re.compile(r"system\s*:\s*(.+)")
STAGE_RE = re.compile(r"STAGE\s+\d+\s+—\s+(.+)")
ADVISORY_RE = re.compile(r"\[(WARNING|CRITICAL)\]\s+([A-Z0-9_]+)")

def run_invariants():
    proc = subprocess.run(
        ["python3", "demos/cluster_monitor_demo.py"],
        cwd=INV_PY,
        text=True,
        capture_output=True,
        check=True,
    )

    lines = proc.stdout.splitlines()

    stages = []
    advisories = []
    current_stage = None
    current_system = None

    for line in lines:
        stage_match = STAGE_RE.search(line)
        if stage_match:
            current_stage = stage_match.group(1).strip()
            current_system = None
            continue

        system_match = SYSTEM_RE.search(line)
        if system_match:
            current_system = system_match.group(1).strip()
            continue

        betti_match = BETTI_RE.search(line)
        if betti_match:
            b0 = int(betti_match.group(1))
            b1 = int(betti_match.group(2))
            stages.append({
                "stage": current_stage,
                "system": current_system,
                "b0": b0,
                "b1": b1
            })
            continue

        advisory_match = ADVISORY_RE.search(line)
        if advisory_match:
            advisories.append({
                "severity": advisory_match.group(1),
                "code": advisory_match.group(2)
            })

    return {
        "engine": "boundary-invariants",
        "stages": stages,
        "advisories": advisories,
        "raw_output": proc.stdout
    }

if __name__ == "__main__":
    print(json.dumps(run_invariants(), indent=2))
