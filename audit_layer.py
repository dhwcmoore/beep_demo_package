"""
audit_layer.py — VeriStrain Scotford
Canonical JSON, provenance tracking, Ed25519 digital signing, and
versioned audit envelope under schema veristrain_industrial_audit.v1.

Replaces the demo-era beep_audit.v1 naming and null-signature approach.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from explanation_engine import ExplanationResult
from fusion_engine import FusionResult
from industrial_schema import PlantObservationBundle


# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION         = "veristrain_industrial_audit.v1"
CANONICALISATION_ALGO  = "json_c14n_v1"
SIGNATURE_ALGORITHM    = "Ed25519"


# ---------------------------------------------------------------------------
# Version manifest
# ---------------------------------------------------------------------------

@dataclass
class VersionManifest:
    """Records all versioned components so any output can be reproduced."""
    program_version:            str
    ruleset_version:            str
    topology_model_version:     str
    schema_version:             str = SCHEMA_VERSION
    site_configuration_version: str = "unset"
    structural_semantics_version: str = "v1"
    rupture_semantics_version:    str = "v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version":                self.schema_version,
            "program_version":               self.program_version,
            "ruleset_version":               self.ruleset_version,
            "topology_model_version":        self.topology_model_version,
            "site_configuration_version":    self.site_configuration_version,
            "structural_semantics_version":  self.structural_semantics_version,
            "rupture_semantics_version":     self.rupture_semantics_version,
        }


# ---------------------------------------------------------------------------
# Provenance record
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceRecord:
    """Tracks data lineage for the evaluation."""
    data_sources:              List[str]
    ingestion_time:            datetime
    processing_window_start:   datetime
    processing_window_end:     datetime
    dropped_input_count:       int       = 0
    inferred_topology_count:   int       = 0
    topology_substitutions:    List[str] = field(default_factory=list)
    missing_critical_tags:     List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_sources":            self.data_sources,
            "ingestion_time":          self.ingestion_time.isoformat(),
            "processing_window_start": self.processing_window_start.isoformat(),
            "processing_window_end":   self.processing_window_end.isoformat(),
            "dropped_input_count":     self.dropped_input_count,
            "inferred_topology_count": self.inferred_topology_count,
            "topology_substitutions":  self.topology_substitutions,
            "missing_critical_tags":   self.missing_critical_tags,
        }


# ---------------------------------------------------------------------------
# Integrity record
# ---------------------------------------------------------------------------

@dataclass
class IntegrityRecord:
    payload_sha256:     str
    canonicalisation:   str = CANONICALISATION_ALGO
    signature_algorithm: str = SIGNATURE_ALGORITHM
    signer:             Optional[str]  = None
    signature:          Optional[str]  = None   # base64url Ed25519 signature
    signing_key_ref:    Optional[str]  = None
    verification_status: str = "unsigned"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonicalisation":    self.canonicalisation,
            "payload_sha256":      self.payload_sha256,
            "signature_algorithm": self.signature_algorithm,
            "signer":              self.signer,
            "signing_key_ref":     self.signing_key_ref,
            "signature":           self.signature,
            "verification_status": self.verification_status,
        }


# ---------------------------------------------------------------------------
# Sealed audit output
# ---------------------------------------------------------------------------

@dataclass
class SealedAuditOutput:
    """
    The canonical output artefact.
    Layout matches the veristrain_industrial_audit.v1 schema.
    """
    schema_version:      str
    created_utc:         str
    site:                str
    plant_area:          str
    operating_mode:      str
    run_mode:            str
    time_window:         Dict[str, str]
    decision_state:      str
    structural_judgement: str
    rupture_judgement:   Optional[str]
    confidence_score:    float
    coverage_score:      float
    observability_status: str
    affected_region:     Optional[str]
    evidence:            List[str]
    escalation_reason:   str
    recommended_action_class: str
    operator_summary:    str
    engineer_detail:     Dict[str, Any]
    provenance:          Dict[str, Any]
    versions:            Dict[str, Any]
    integrity:           Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version":          self.schema_version,
            "created_utc":             self.created_utc,
            "site":                    self.site,
            "plant_area":              self.plant_area,
            "operating_mode":          self.operating_mode,
            "run_mode":                self.run_mode,
            "time_window":             self.time_window,
            "decision_state":          self.decision_state,
            "structural_judgement":    self.structural_judgement,
            "rupture_judgement":       self.rupture_judgement,
            "confidence_score":        round(self.confidence_score, 4),
            "coverage_score":          round(self.coverage_score, 4),
            "observability_status":    self.observability_status,
            "affected_region":         self.affected_region,
            "evidence":                self.evidence,
            "escalation_reason":       self.escalation_reason,
            "recommended_action_class": self.recommended_action_class,
            "operator_summary":        self.operator_summary,
            "engineer_detail":         self.engineer_detail,
            "provenance":              self.provenance,
            "versions":                self.versions,
            "integrity":               self.integrity,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


# ---------------------------------------------------------------------------
# Audit layer
# ---------------------------------------------------------------------------

class AuditLayer:
    """
    Assembles and seals the final veristrain_industrial_audit.v1 output.

    Signing is done via an optional signer callable that accepts the
    canonical payload bytes and returns a base64url signature string.
    If no signer is provided the output is hashed but unsigned.
    """

    def __init__(
        self,
        version_manifest:  VersionManifest,
        signer:            Optional[Any] = None,   # callable(bytes) -> str
        signer_identity:   Optional[str] = None,
        signing_key_ref:   Optional[str] = None,
    ):
        self.version_manifest = version_manifest
        self.signer           = signer
        self.signer_identity  = signer_identity
        self.signing_key_ref  = signing_key_ref

    def seal(
        self,
        bundle:      PlantObservationBundle,
        fusion:      FusionResult,
        explanation: ExplanationResult,
        provenance:  ProvenanceRecord,
    ) -> SealedAuditOutput:
        now_utc = datetime.now(timezone.utc).isoformat()

        # Derive rupture judgement label from dominant event
        rupture_judgement = self._rupture_label(fusion)

        # Assemble payload (without integrity — computed separately)
        payload: Dict[str, Any] = {
            "schema_version":       SCHEMA_VERSION,
            "created_utc":          now_utc,
            "site":                 bundle.site,
            "plant_area":           bundle.plant_area,
            "operating_mode":       bundle.operating_mode.value,
            "run_mode":             bundle.run_mode.value,
            "time_window": {
                "start": bundle.window_start.isoformat(),
                "end":   bundle.window_end.isoformat(),
            },
            "decision_state":          fusion.decision_state.value,
            "structural_judgement":    fusion.structural.primary_judgement.value,
            "rupture_judgement":       rupture_judgement,
            "confidence_score":        round(fusion.confidence_score, 4),
            "coverage_score":          round(fusion.coverage_score, 4),
            "observability_status":    fusion.observability_status,
            "affected_region":         explanation.affected_region,
            "evidence":                explanation.evidence,
            "escalation_reason":       explanation.escalation_reason,
            "recommended_action_class": explanation.recommended_action_class,
            "operator_summary":        explanation.operator_summary,
            "engineer_detail":         explanation.engineer_detail,
            "provenance":              provenance.to_dict(),
            "versions":                self.version_manifest.to_dict(),
        }

        # Canonical JSON → SHA-256
        canonical = _canonical_json(payload)
        payload_hash = hashlib.sha256(canonical).hexdigest()

        # Sign if signer available
        sig_value: Optional[str] = None
        verification_status = "unsigned"
        if self.signer is not None:
            try:
                sig_value = self.signer(canonical)
                verification_status = "signed"
            except Exception as exc:
                verification_status = f"signing_failed: {exc}"

        integrity = IntegrityRecord(
            payload_sha256=payload_hash,
            signer=self.signer_identity,
            signing_key_ref=self.signing_key_ref,
            signature=sig_value,
            verification_status=verification_status,
        )

        return SealedAuditOutput(
            schema_version=SCHEMA_VERSION,
            created_utc=now_utc,
            site=bundle.site,
            plant_area=bundle.plant_area,
            operating_mode=bundle.operating_mode.value,
            run_mode=bundle.run_mode.value,
            time_window={
                "start": bundle.window_start.isoformat(),
                "end":   bundle.window_end.isoformat(),
            },
            decision_state=fusion.decision_state.value,
            structural_judgement=fusion.structural.primary_judgement.value,
            rupture_judgement=rupture_judgement,
            confidence_score=fusion.confidence_score,
            coverage_score=fusion.coverage_score,
            observability_status=fusion.observability_status,
            affected_region=explanation.affected_region,
            evidence=explanation.evidence,
            escalation_reason=explanation.escalation_reason,
            recommended_action_class=explanation.recommended_action_class,
            operator_summary=explanation.operator_summary,
            engineer_detail=explanation.engineer_detail,
            provenance=provenance.to_dict(),
            versions=self.version_manifest.to_dict(),
            integrity=integrity.to_dict(),
        )

    @staticmethod
    def verify(sealed: SealedAuditOutput) -> bool:
        """
        Recompute the SHA-256 over the payload and compare to stored hash.
        Returns True if the payload is unmodified since sealing.
        Signature cryptographic verification requires the public key and is
        handled separately.
        """
        d = sealed.to_dict()
        integrity = d.pop("integrity")
        canonical = _canonical_json(d)
        computed = hashlib.sha256(canonical).hexdigest()
        return computed == integrity["payload_sha256"]

    @staticmethod
    def _rupture_label(fusion: FusionResult) -> Optional[str]:
        from signal_analysis import ProcessEventType
        dominant = fusion.signal.dominant_event
        if dominant is None:
            return None
        labels = {
            ProcessEventType.PRESSURE_DRIFT:   "RJ_PersistentPressureDivergence",
            ProcessEventType.PRESSURE_SPIKE:   "RJ_PressureSpike",
            ProcessEventType.FLOW_COLLAPSE:    "RJ_FlowCollapse",
            ProcessEventType.UNSTABLE_OSCILLATION: "RJ_UnstableOscillation",
            ProcessEventType.SENSOR_DISAGREEMENT: "RJ_SensorDisagreement",
            ProcessEventType.CONTROL_RESPONSE_ABSENT: "RJ_ControlResponseAbsent",
            ProcessEventType.LOSS_OF_EXPECTED_CORRELATION: "RJ_CorrelationLoss",
            ProcessEventType.THERMAL_IMBALANCE: "RJ_ThermalImbalance",
        }
        return labels.get(dominant, f"RJ_{dominant.value}")


# ---------------------------------------------------------------------------
# Ed25519 signer helper (requires `cryptography` package)
# ---------------------------------------------------------------------------

def make_ed25519_signer(private_key_pem: bytes):
    """
    Returns a callable(bytes) -> str suitable for AuditLayer(signer=...).
    Requires: pip install cryptography
    The returned string is a base64url-encoded Ed25519 signature.
    """
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key: Ed25519PrivateKey = load_pem_private_key(private_key_pem, password=None)

    def sign(payload_bytes: bytes) -> str:
        raw_sig = key.sign(payload_bytes)
        return base64.urlsafe_b64encode(raw_sig).decode("ascii")

    return sign


# ---------------------------------------------------------------------------
# Canonical JSON
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> bytes:
    """
    RFC 7159 canonical JSON: sorted keys, no extra whitespace, UTF-8.
    Floats are serialised with full precision.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
