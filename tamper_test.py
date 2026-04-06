#!/usr/bin/env python3
"""
Tamper test for VeriBound-core sealed BEEP artefacts.

This script demonstrates that the integrity seal properly fails when the
payload is modified, proving the integrity layer is not ornamental.
"""

import json
import sys
from pathlib import Path

from veribound_core.verify import verify_sha256_hex

PROJECT_ROOT = Path(__file__).resolve().parent
SEALED_PATH = PROJECT_ROOT / "output" / "beep_output_sealed.json"


def load_sealed() -> dict:
    if not SEALED_PATH.exists():
        raise FileNotFoundError(f"Sealed BEEP output not found: {SEALED_PATH}")

    with SEALED_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def tamper_payload(payload: dict) -> dict:
    """
    Tamper with the payload by changing the risk level.
    This simulates an attacker modifying the assessment result.
    """
    tampered = payload.copy()
    tampered["risk_level"] = "LOW"  # Change from CRITICAL to LOW
    return tampered


def main() -> None:
    print("🔍 VeriBound-Core Tamper Test")
    print("=" * 50)

    # Load the sealed artefact
    sealed = load_sealed()
    payload = sealed["payload"]
    integrity = sealed["integrity"]
    expected_hash = integrity["payload_sha256"]

    print(f"📄 Loaded sealed artefact: {SEALED_PATH}")
    print(f"🔒 Original payload hash: {expected_hash}")
    print(f"📊 Original risk level: {payload['risk_level']}")

    # Verify original (should pass)
    original_ok = verify_sha256_hex(payload, expected_hash)
    print(f"✅ Original verification: {'PASS' if original_ok else 'FAIL'}")

    # Tamper with the payload
    tampered_payload = tamper_payload(payload)
    print(f"🛠️  Tampered risk level: {tampered_payload['risk_level']}")

    # Verify tampered (should fail)
    tampered_ok = verify_sha256_hex(tampered_payload, expected_hash)
    print(f"❌ Tampered verification: {'PASS' if tampered_ok else 'FAIL'}")

    print("\n" + "=" * 50)
    if original_ok and not tampered_ok:
        print("🎉 SUCCESS: Integrity seal correctly rejects tampered payload!")
        print("   The VeriBound-core layer is working as intended.")
    else:
        print("💥 FAILURE: Integrity check did not behave as expected.")
        sys.exit(1)


if __name__ == "__main__":
    main()