import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
INVARIANT_DIR = PROJECT_ROOT / "invariant_engine" / "python"
DEMO_SCRIPT = INVARIANT_DIR / "demos" / "cluster_monitor_demo.py"
OCAML_DIR = PROJECT_ROOT / "ocaml"
STRUCTURAL_CLASSIFIER = OCAML_DIR / "_build" / "default" / "structural_judgement.exe"

BETTI_LINE_RE = re.compile(r"^(Nominal|Fault)\s+Betti:\s*\{0:\s*(\d+),\s*1:\s*(\d+)\}\s*$")


def build_structural_classifier() -> None:
    if not OCAML_DIR.exists():
        raise FileNotFoundError(f"OCaml directory not found: {OCAML_DIR}")

    subprocess.run(
        ["dune", "build", "structural_judgement.exe"],
        cwd=str(OCAML_DIR),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )


def classify_structural_judgement(nominal_betti: dict, fault_betti: dict) -> str:
    if not nominal_betti or not fault_betti:
        return "NoBreak"

    if not STRUCTURAL_CLASSIFIER.exists():
        build_structural_classifier()

    nominal_b0 = nominal_betti.get("b0", 0)
    nominal_b1 = nominal_betti.get("b1", 0)
    fault_b0 = fault_betti.get("b0", 0)
    fault_b1 = fault_betti.get("b1", 0)

    proc = subprocess.run(
        [
            str(STRUCTURAL_CLASSIFIER),
            str(nominal_b0),
            str(nominal_b1),
            str(fault_b0),
            str(fault_b1),
        ],
        cwd=str(OCAML_DIR),
        text=True,
        capture_output=True,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            "Structural classifier failed.\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}"
        )

    return proc.stdout.strip()


def generate_advisories(nominal_betti: dict, fault_betti: dict) -> list[dict]:
    advisories = []

    db0 = fault_betti.get("b0", 0) - nominal_betti.get("b0", 0)
    db1 = fault_betti.get("b1", 0) - nominal_betti.get("b1", 0)

    if db0 > 0:
        advisories.append({
            "code": "CONNECTIVITY_PARTITION",
            "severity": "CRITICAL",
            "delta_b0": db0,
            "message": (
                f"Connected components increased from {nominal_betti.get('b0')} "
                f"to {fault_betti.get('b0')}."
            ),
        })

    if db1 < 0:
        advisories.append({
            "code": "CLUSTER_RING_VIOLATED",
            "severity": "WARNING",
            "delta_b1": db1,
            "message": (
                f"Cycle count dropped from {nominal_betti.get('b1')} "
                f"to {fault_betti.get('b1')}."
            ),
        })

    if db1 > 0:
        advisories.append({
            "code": "UNEXPECTED_CYCLE",
            "severity": "WARNING",
            "delta_b1": db1,
            "message": (
                f"Cycle count increased from {nominal_betti.get('b1')} "
                f"to {fault_betti.get('b1')}."
            ),
        })

    if not advisories:
        advisories.append({
            "code": "NOMINAL",
            "severity": "OK",
            "message": "No structural violation detected.",
        })

    return advisories


def parse_demo_output(raw_output: str) -> tuple[dict, dict]:
    nominal = {}
    fault = {}

    for line in raw_output.splitlines():
        match = BETTI_LINE_RE.match(line.strip())
        if not match:
            continue

        label = match.group(1)
        b0 = int(match.group(2))
        b1 = int(match.group(3))

        if label == "Nominal":
            nominal = {"b0": b0, "b1": b1}
        elif label == "Fault":
            fault = {"b0": b0, "b1": b1}

    return nominal, fault


def run_invariants() -> dict:
    if not INVARIANT_DIR.exists():
        raise FileNotFoundError(f"Invariant directory not found: {INVARIANT_DIR}")

    if not DEMO_SCRIPT.exists():
        raise FileNotFoundError(f"Demo script not found: {DEMO_SCRIPT}")

    proc = subprocess.run(
        [sys.executable, str(DEMO_SCRIPT)],
        cwd=str(INVARIANT_DIR),
        text=True,
        capture_output=True,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            "Invariant engine failed.\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}"
        )

    nominal_betti, fault_betti = parse_demo_output(proc.stdout)
    advisories = generate_advisories(nominal_betti, fault_betti)
    structural_judgement = classify_structural_judgement(nominal_betti, fault_betti)
    structural_inputs = {
        "nominal_b0": nominal_betti.get("b0", 0),
        "nominal_b1": nominal_betti.get("b1", 0),
        "fault_b0": fault_betti.get("b0", 0),
        "fault_b1": fault_betti.get("b1", 0),
    }

    return {
        "engine": "boundary-invariants",
        "mode": "real",
        "nominal_betti": nominal_betti,
        "fault_betti": fault_betti,
        "structural_inputs": structural_inputs,
        "structural_judgement": structural_judgement,
        "structural_judgement_source": "ocaml",
        "structural_semantics_version": "v1",
        "advisories": advisories,
        "raw_output": proc.stdout,
    }


if __name__ == "__main__":
    print(json.dumps(run_invariants(), indent=2))