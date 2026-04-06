import json
from pathlib import Path

from veribound_core.verify import verify_sha256_hex

PROJECT_ROOT = Path(__file__).resolve().parent
SEALED_PATH = PROJECT_ROOT / "output" / "beep_output_sealed.json"


def main() -> None:
    if not SEALED_PATH.exists():
        raise FileNotFoundError(f"Sealed BEEP output not found: {SEALED_PATH}")

    with SEALED_PATH.open("r", encoding="utf-8") as f:
        sealed = json.load(f)

    payload = sealed.get("payload")
    integrity = sealed.get("integrity", {})
    expected_hash = integrity.get("payload_sha256")

    if payload is None:
        raise ValueError("Sealed artefact missing 'payload'.")
    if not expected_hash:
        raise ValueError("Sealed artefact missing integrity.payload_sha256.")

    ok = verify_sha256_hex(payload, expected_hash)

    result = {
        "sealed_output": str(SEALED_PATH),
        "verification_ok": ok,
        "expected_hash": expected_hash,
        "seal_type": integrity.get("seal_type"),
        "seal_version": integrity.get("seal_version"),
    }

    print(json.dumps(result, indent=2))

    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()