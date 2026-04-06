import json
import os
from datetime import datetime, timezone
from pathlib import Path

from veribound_core.verify import sha256_hex_for_object, verify_sha256_hex

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"

RAW_PATH = OUTPUT_DIR / "beep_output.json"
SEALED_PATH = OUTPUT_DIR / "beep_output_sealed.json"


def load_raw_payload() -> dict:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Raw BEEP output not found: {RAW_PATH}")

    with RAW_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Raw BEEP output must be a JSON object.")

    return data


def build_sealed_envelope(payload: dict) -> dict:
    payload_hash = sha256_hex_for_object(payload)

    semantic_contracts = payload.get("semantic_contracts", {})
    structural_semantics_version = payload.get(
        "structural_semantics_version",
        semantic_contracts.get("structural_semantics_version"),
    )
    rupture_semantics_version = payload.get(
        "rupture_semantics_version",
        semantic_contracts.get("rupture_semantics_version"),
    )
    guardrails_enforced = semantic_contracts.get("guardrails_enforced", None)

    envelope = {
        "schema_version": "beep_audit.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "integrity": {
            "canonicalisation": "json_c14n_v1",
            "payload_sha256": payload_hash,
            "seal_type": "veribound-core",
            "seal_version": "v1",
            "signature": None,
        },
        "verification": {
            "structural_semantics_version": structural_semantics_version,
            "rupture_semantics_version": rupture_semantics_version,
            "guardrails_enforced": guardrails_enforced,
            "verified_at_seal_time": verify_sha256_hex(payload, payload_hash),
        },
    }

    return envelope


def write_sealed_envelope(envelope: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with SEALED_PATH.open("w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)

    os.chmod(SEALED_PATH, 0o644)


def main() -> None:
    payload = load_raw_payload()
    envelope = build_sealed_envelope(payload)
    write_sealed_envelope(envelope)

    print(json.dumps({
        "sealed_output": str(SEALED_PATH),
        "payload_sha256": envelope["integrity"]["payload_sha256"],
        "seal_type": envelope["integrity"]["seal_type"],
        "seal_version": envelope["integrity"]["seal_version"],
        "verified_at_seal_time": envelope["verification"]["verified_at_seal_time"],
    }, indent=2))


if __name__ == "__main__":
    main()