"""
explanation_engine.py — VeriStrain Scotford
Causal explanation extraction from fusion results.
Produces two output modes:
  - Operator mode: plain language, actionable
  - Engineer mode: detailed evidence chain, sensor IDs, rule trail, Betti deltas
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fusion_engine import ActionClass, FiredRule, FusionResult, OperationalState
from signal_analysis import AnomalyPersistence, ProcessEvent, ProcessEventType
from structural_analysis import StructuralJudgement, StructuralAnalysisResult


# ---------------------------------------------------------------------------
# Explanation objects
# ---------------------------------------------------------------------------

@dataclass
class MinimalEvidenceSet:
    """
    The smallest set of observations/facts sufficient to explain the decision.
    Lets an engineer see exactly what drove the result and what could disconfirm it.
    """
    items:           List[str]
    disconfirmers:   List[str]   # what evidence would weaken or reverse this
    evidence_robust: bool        # True if multiple independent signals agree


@dataclass
class ExplanationResult:
    """
    Full explanation output for one evaluation, in both operator and engineer forms.
    """
    # Common fields
    structural_judgement: str
    affected_region:      Optional[str]
    escalation_reason:    str
    recommended_action_class: str
    evidence:             List[str]
    minimal_evidence_set: MinimalEvidenceSet

    # Operator mode
    operator_summary:     str    # one or two plain-language sentences

    # Engineer mode
    engineer_detail:      Dict[str, Any]

    def to_dict(self, mode: str = "engineer") -> Dict[str, Any]:
        """
        mode: "operator" | "engineer"
        """
        base = {
            "structural_judgement":     self.structural_judgement,
            "affected_region":          self.affected_region,
            "evidence":                 self.evidence,
            "escalation_reason":        self.escalation_reason,
            "recommended_action_class": self.recommended_action_class,
        }
        if mode == "operator":
            base["summary"] = self.operator_summary
        else:
            base["minimal_evidence_set"] = {
                "items":           self.minimal_evidence_set.items,
                "disconfirmers":   self.minimal_evidence_set.disconfirmers,
                "evidence_robust": self.minimal_evidence_set.evidence_robust,
            }
            base["engineer_detail"] = self.engineer_detail
        return base


# ---------------------------------------------------------------------------
# Explanation engine
# ---------------------------------------------------------------------------

class ExplanationEngine:
    """
    Derives causal explanations from a FusionResult.
    Stateless — call explain() for each result.
    """

    def explain(self, result: FusionResult) -> ExplanationResult:
        structural = result.structural
        signal     = result.signal
        state      = result.decision_state
        sj         = structural.primary_judgement

        # Primary affected region (worst-criticality region that appears in evidence)
        affected_region = (
            structural.affected_regions[0] if structural.affected_regions else None
        )

        # Evidence assembly (structural + signal, deduplicated)
        evidence = list(structural.evidence)
        for event in signal.events:
            for e in event.evidence:
                if e not in evidence:
                    evidence.append(e)
        for alert in signal.multi_signal_alerts:
            if alert not in evidence:
                evidence.append(alert)

        # Escalation reason
        escalation_reason = self._build_escalation_reason(state, sj, result)

        # Recommended action label (first action)
        action_label = (
            result.recommended_actions[0].value
            if result.recommended_actions
            else ActionClass.MONITOR.value
        )

        # Minimal evidence set
        minimal = self._minimal_evidence(result)

        # Operator summary
        operator_summary = self._operator_sentence(state, sj, affected_region, result)

        # Engineer detail
        engineer_detail = self._engineer_detail(result)

        return ExplanationResult(
            structural_judgement=sj.value,
            affected_region=affected_region,
            escalation_reason=escalation_reason,
            recommended_action_class=action_label,
            evidence=evidence,
            minimal_evidence_set=minimal,
            operator_summary=operator_summary,
            engineer_detail=engineer_detail,
        )

    # ------------------------------------------------------------------
    # Escalation reason
    # ------------------------------------------------------------------

    def _build_escalation_reason(
        self,
        state: OperationalState,
        sj: StructuralJudgement,
        result: FusionResult,
    ) -> str:
        parts: List[str] = []

        sj_phrases = {
            StructuralJudgement.SJ_Normal:
                "no structural break detected",
            StructuralJudgement.SJ_CycleLoss:
                "loss of closed-loop path in functional graph",
            StructuralJudgement.SJ_RedundancyLoss:
                "loss of functional redundancy in active flow loop",
            StructuralJudgement.SJ_IsolationEmerging:
                "material flow paths becoming isolated",
            StructuralJudgement.SJ_PartialPartition:
                "partial partition of connected regions",
            StructuralJudgement.SJ_FullPartition:
                "full graph partition — plant split into disconnected sections",
            StructuralJudgement.SJ_PathMismatch:
                "multiple flow paths inactive simultaneously",
            StructuralJudgement.SJ_FlowStorageContradiction:
                "active material flow with inactive relief paths",
            StructuralJudgement.SJ_ControlLoopInstability:
                "control dependency edges broken",
            StructuralJudgement.SJ_NonClosableState:
                "system cannot be brought to safe closure — control and relief paths lost",
            StructuralJudgement.SJ_ContainmentRisk:
                "containment boundary compromised or unobservable",
            StructuralJudgement.SJ_CoupledEscalationRisk:
                "multiple critical structural failures simultaneously active",
        }
        parts.append(sj_phrases.get(sj, sj.value))

        # Signal contribution
        dominant = result.signal.dominant_event
        if dominant:
            signal_phrases = {
                ProcessEventType.PRESSURE_DRIFT:   "combined with persistent upstream pressure drift",
                ProcessEventType.PRESSURE_SPIKE:   "combined with pressure spike",
                ProcessEventType.FLOW_COLLAPSE:    "combined with flow collapse",
                ProcessEventType.SENSOR_DISAGREEMENT: "combined with sensor disagreement across boundary",
                ProcessEventType.CONTROL_RESPONSE_ABSENT: "combined with absent control response",
                ProcessEventType.UNSTABLE_OSCILLATION: "combined with unstable oscillation",
            }
            phrase = signal_phrases.get(dominant)
            if phrase:
                parts.append(phrase)

        # Rule firing contribution
        if result.fired_rules:
            rule_descs = [r.description for r in result.fired_rules[:2]]
            parts.append("escalated by rules: " + "; ".join(rule_descs))

        # Observability
        if result.observability_status == "critically_under_observed":
            parts.append("decision confidence limited by poor sensor coverage")

        return "; ".join(parts) + "."

    # ------------------------------------------------------------------
    # Minimal evidence set
    # ------------------------------------------------------------------

    def _minimal_evidence(self, result: FusionResult) -> MinimalEvidenceSet:
        structural = result.structural
        signal     = result.signal

        items: List[str] = []

        # Structural: the specific edge losses that fired the primary judgement
        if structural.lost_material_paths:
            items.append(
                f"Material flow path(s) inactive: "
                + ", ".join(
                    f"{e.source}→{e.target}" for e in structural.lost_material_paths[:3]
                )
            )
        if structural.lost_relief_paths:
            items.append(
                f"Relief path(s) inactive: "
                + ", ".join(
                    f"{e.source}→{e.target}" for e in structural.lost_relief_paths[:3]
                )
            )
        if structural.lost_control_dependencies:
            items.append(
                f"Control dependency edge(s) broken: "
                + ", ".join(
                    f"{e.source}→{e.target}" for e in structural.lost_control_dependencies[:3]
                )
            )

        # Signal: the specific events with highest magnitude
        top_events = sorted(signal.events, key=lambda e: e.magnitude, reverse=True)[:3]
        for e in top_events:
            items.append(
                f"{e.event_type.value} on {', '.join(e.component_ids)} "
                f"(magnitude {e.magnitude:.2f}, {e.persistence.value})"
            )

        # Fired rules
        for rule in result.fired_rules[:2]:
            items.append(f"Rule {rule.rule_id}: {rule.description}")

        # What would disconfirm this
        disconfirmers: List[str] = []
        sj = structural.primary_judgement
        if sj in (StructuralJudgement.SJ_RedundancyLoss, StructuralJudgement.SJ_CycleLoss):
            disconfirmers.append(
                "Confirmation that alternative path is physically available and not just administratively closed"
            )
        if sj == StructuralJudgement.SJ_ContainmentRisk:
            disconfirmers.append(
                "Restoration of measurement observability in the affected region"
            )
        if any(e.event_type == ProcessEventType.SENSOR_DISAGREEMENT for e in signal.events):
            disconfirmers.append(
                "Independent confirmation that the disagreeing sensors are both calibrated"
            )
        disconfirmers.append(
            "Observation of normal operating conditions across the full evaluation window"
        )

        # Evidence robust if structural and signal agree, and coverage is good
        robust = (
            structural.structural_break
            and signal.rupture_score > 0.0
            and result.coverage_score >= 0.75
        )

        return MinimalEvidenceSet(
            items=items,
            disconfirmers=disconfirmers,
            evidence_robust=robust,
        )

    # ------------------------------------------------------------------
    # Operator summary (plain language)
    # ------------------------------------------------------------------

    def _operator_sentence(
        self,
        state: OperationalState,
        sj: StructuralJudgement,
        region: Optional[str],
        result: FusionResult,
    ) -> str:
        region_phrase = f" in {region}" if region else ""
        dominant = result.signal.dominant_event

        state_lead = {
            OperationalState.STATE_Normal:
                "Operating conditions appear normal.",
            OperationalState.STATE_Monitor:
                "Minor anomaly detected — monitoring recommended.",
            OperationalState.STATE_Watch:
                f"Developing condition{region_phrase} — closer watch advised.",
            OperationalState.STATE_HighRisk:
                f"High-risk condition{region_phrase} — prompt inspection required.",
            OperationalState.STATE_Critical:
                f"Critical condition{region_phrase} — operator and engineering review required.",
            OperationalState.STATE_Critical_IsolationReview:
                f"Critical condition{region_phrase} with containment concern — isolation review required immediately.",
            OperationalState.STATE_Critical_OperatorEscalation:
                f"Critical condition{region_phrase} — immediate operator escalation required.",
            OperationalState.STATE_Inconclusive:
                "Assessment inconclusive due to data coverage — data quality investigation required.",
        }

        sj_detail = {
            StructuralJudgement.SJ_Normal:                   "",
            StructuralJudgement.SJ_CycleLoss:               "Feed loop closure has been lost.",
            StructuralJudgement.SJ_RedundancyLoss:          "Feed loop redundancy appears lost.",
            StructuralJudgement.SJ_IsolationEmerging:       "Material flow paths are becoming isolated.",
            StructuralJudgement.SJ_PartialPartition:        "Part of the plant is becoming disconnected.",
            StructuralJudgement.SJ_FullPartition:           "Plant has split into disconnected sections.",
            StructuralJudgement.SJ_PathMismatch:            "Multiple flow paths are simultaneously inactive.",
            StructuralJudgement.SJ_FlowStorageContradiction: "Flow is active but relief paths are not.",
            StructuralJudgement.SJ_ControlLoopInstability:  "Control loop connections appear broken.",
            StructuralJudgement.SJ_NonClosableState:        "System may not be closable safely — control and relief paths are both lost.",
            StructuralJudgement.SJ_ContainmentRisk:         "Containment boundary may be compromised or not observable.",
            StructuralJudgement.SJ_CoupledEscalationRisk:   "Multiple serious structural failures are occurring together.",
        }

        signal_detail = ""
        if dominant == ProcessEventType.PRESSURE_DRIFT:
            signal_detail = " Upstream pressure is rising persistently."
        elif dominant == ProcessEventType.FLOW_COLLAPSE:
            signal_detail = " Flow has dropped significantly."
        elif dominant == ProcessEventType.SENSOR_DISAGREEMENT:
            signal_detail = " Sensor readings are inconsistent."
        elif dominant == ProcessEventType.PRESSURE_SPIKE:
            signal_detail = " A pressure spike has been detected."
        elif dominant == ProcessEventType.CONTROL_RESPONSE_ABSENT:
            signal_detail = " A control action did not produce an expected response."

        lead   = state_lead.get(state, state.value)
        struct = sj_detail.get(sj, "")
        return f"{lead} {struct}{signal_detail}".strip()

    # ------------------------------------------------------------------
    # Engineer detail
    # ------------------------------------------------------------------

    def _engineer_detail(self, result: FusionResult) -> Dict[str, Any]:
        structural = result.structural
        signal     = result.signal

        return {
            "betti_comparison": {
                "physical_b0":   structural.physical_b0,
                "physical_b1":   structural.physical_b1,
                "functional_b0": structural.functional_b0,
                "functional_b1": structural.functional_b1,
                "delta_b0":      structural.functional_b0 - structural.physical_b0,
                "delta_b1":      structural.functional_b1 - structural.physical_b1,
            },
            "structural_judgements": {
                "primary":     structural.primary_judgement.value,
                "secondary":   [sj.value for sj in structural.secondary_judgements],
                "invariant_score": round(structural.invariant_score, 4),
            },
            "typed_edge_losses": {
                "material_flow": [
                    {"source": e.source, "target": e.target, "stream": e.stream_id}
                    for e in structural.lost_material_paths
                ],
                "control_dependency": [
                    {"source": e.source, "target": e.target}
                    for e in structural.lost_control_dependencies
                ],
                "relief_path": [
                    {"source": e.source, "target": e.target}
                    for e in structural.lost_relief_paths
                ],
            },
            "signal_events": [e.to_dict() for e in signal.events],
            "multi_signal_alerts": signal.multi_signal_alerts,
            "rupture_score": round(signal.rupture_score, 4),
            "fired_rules": [
                {"rule_id": r.rule_id, "result": r.result.value, "description": r.description}
                for r in result.fired_rules
            ],
            "suppressed_rules": [
                {"rule_id": r.rule_id, "description": r.description}
                for r in result.suppressed_rules
            ],
            "coverage_score":     round(result.coverage_score, 4),
            "confidence_score":   round(result.confidence_score, 4),
            "observability_status": result.observability_status,
            "disconnected_regions":  structural.disconnected_regions,
            "unobservable_regions":  structural.unobservable_regions,
        }
