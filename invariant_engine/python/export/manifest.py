"""
manifest.py — Optional run metadata manifest (sidecar to the audit payload).

A run manifest records provenance for a single export run: when it happened,
which engine produced the payload, where the output file was written, and the
payload hash.  It is NOT a substitute for the payload itself; it is a
lightweight audit trail that tools can parse without loading the full payload.

Manifest format: run_manifest.v1
"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _now_utc_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_run_manifest(
    *,
    output_path: str,
    payload_sha256: str,
    schema_version: str,
    engine: str,
    engine_version: str,
    audit_id: str,
    created_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a run manifest dict.

    Parameters
    ----------
    output_path:
        Absolute (or relative) path to the written payload JSON file.
    payload_sha256:
        The 64-character hex SHA-256 of the payload, as stored in
        payload["integrity"]["payload_sha256"].
    schema_version:
        The schema_version field from the payload (e.g. "audit_invariants.v1").
    engine, engine_version:
        Source identifiers copied from payload["source"].
    audit_id:
        The audit_id from the payload.
    created_utc:
        Override the manifest timestamp; defaults to now().
    """
    return {
        "manifest_version": "run_manifest.v1",
        "created_utc": created_utc or _now_utc_rfc3339(),
        "audit_id": audit_id,
        "schema_version": schema_version,
        "engine": engine,
        "engine_version": engine_version,
        "output_file": os.fspath(output_path),
        "payload_sha256": payload_sha256,
    }


def build_run_manifest_from_payload(
    output_path: str,
    payload: Dict[str, Any],
    created_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper: extract all manifest fields from a completed payload dict.

    The payload must already have ``integrity.payload_sha256`` set
    (i.e. ``build_v1_payload`` must have been called first).
    """
    return build_run_manifest(
        output_path=output_path,
        payload_sha256=payload["integrity"]["payload_sha256"],
        schema_version=payload["schema_version"],
        engine=payload["source"]["engine"],
        engine_version=payload["source"]["engine_version"],
        audit_id=payload["audit_id"],
        created_utc=created_utc,
    )


def write_run_manifest(path: str, manifest: Dict[str, Any]) -> None:
    """Write the manifest dict to *path* as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
