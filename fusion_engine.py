"""
fusion_engine.py — VeriStrain Scotford
Process-state decision engine replacing the plain composite score.

Combines structural and signal analysis results under explicit rules,
contextual suppression, observability weighting, and area-aware escalation.
Emits a named operational state, not a floating-point label.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from industrial_schema import OperatingMode, SafetyCriticality
from signal_analysis import AnomalyPersistence, ProcessEventType, SignalAnalysisResult
from structural_analysis import StructuralJudgement, StructuralAnalysisResult


# ---------------------------------------------------------------------------
# Operational states
# ---------------------------------------------------------------------------

class OperationalState(str, Enum):
    STATE_Normal                     = "STATE_Normal"
    STATE_Monitor                    = "STATE_Monitor"
    STATE_Watch                      = "STATE_Watch"
    STATE_HighRisk                   = "STATE_HighRisk"
    STATE_Critical                   = "STATE_Critical"
    STATE_Critical_IsolationReview   = "STATE_Critical_IsolationReview"
    STATE_Critical_OperatorEscalation = "STATE_Critical_OperatorEscalation"
    STATE_Inconclusive               = "STATE_Inconclusive"


# Severity ordering
_STATE_SEVERITY: Dict[OperationalState, int] = {
    OperationalState.STATE_Normal:                      0,
    OperationalState.STATE_Monitor:                     1,
    OperationalState.STATE_Watch:                       2,
    OperationalState.STATE_HighRisk:                    3,
    OperationalState.STATE_Inconclusive:                3,
    OperationalState.STATE_Critical:                    4,
    OperationalState.STATE_Critical_IsolationReview:    5,
    OperationalState.STATE_Critical_OperatorEscalation: 6,
}


def state_severity(s: OperationalState) -> int:
    return _STATE_SEVERITY.get(s, 0)


def max_state(*states: OperationalState) -> OperationalState:
    return max(states, key=state_severity)


# ---------------------------------------------------------------------------
# Action classes
# ---------------------------------------------------------------------------

class ActionClass(str, Enum):
    MONITOR                    = "monitor"
    INSPECT_LOCAL              = "inspect_local"
    INSPECT_CROSS_UNIT         = "inspect_cross_unit"
    OPERATOR_REVIEW            = "operator_review"
    ENGINEERING_REVIEW         = "engineering_review"
    ISOLATION_REVIEW           = "isolation_review"
    SHUTDOWN_CONSIDERATION     = "shutdown_consideration"
    DATA_QUALITY_INVESTIGATION = "data_quality_investigation"


# ---------------------------------------------------------------------------
# Rule firing record
# ---------------------------------------------------------------------------

@dataclass
class FiredRule:
    rule_id:     str
    description: str
    result:      OperationalState
    suppressed:  bool = False


# ---------------------------------------------------------------------------
# Suppression context
# ---------------------------------------------------------------------------

@dataclass
class SuppressionContext:
    """
    Declares plant states where certain anomalies are expected or authorised.
    Prevents false positives during planned operations.
    """
    planned_maintenance:    bool = False
    declared_shutdown:      bool = False
    authorised_isolation:   List[str] = field(default_factory=list)  # component IDs
    authorised_bypass:      List[str] = field(default_factory=list)  # region IDs
    minimum_evidence_factor: float = 1.0  # raise to require stronger evidence

    @classmethod
    def from_operating_mode(cls, mode: OperatingMode) -> "SuppressionContext":
        if mode == OperatingMode.MAINTENANCE_BYPASS:
            return cls(planned_maintenance=True, minimum_evidence_factor=2.0)
        if mode == OperatingMode.SHUTDOWN:
            return cls(declared_shutdown=True, minimum_evidence_factor=3.0)
        if mode == OperatingMode.STARTUP:
            return cls(minimum_evidence_factor=1.5)
        return cls()


# ---------------------------------------------------------------------------
# Fusion configuration
# ---------------------------------------------------------------------------

@dataclass
class FusionConfig:
    structural_weight:  float = 0.50
    signal_weight:      float = 0.50

    # Score thresholds for base state assignment
    threshold_critical: float = 7.0
    threshold_high:     float = 4.0
    threshold_watch:    float = 2.5
    threshold_monitor:  float = 1.0

    # Coverage thresholds below which Inconclusive is forced
    min_coverage_for_normal: float = 0.70
    min_coverage_for_high:   float = 0.50

    # Site criticality multipliers
    criticality_multiplier: Dict[str, float] = field(default_factory=lambda: {
        SafetyCriticality.LOW.value:            0.8,
        SafetyCriticality.MODERATE.value:       1.0,
        SafetyCriticality.HIGH.value:           1.3,
        SafetyCriticality.SAFETY_CRITICAL.value: 1.7,
    })


# ---------------------------------------------------------------------------
# Fusion result
# ---------------------------------------------------------------------------

@dataclass
class FusionResult:
    """
    The primary output of the fusion engine for one evaluation window.
    This is what gets passed to the explanation engine and audit layer.
    """
    decision_state:       OperationalState
    recommended_actions:  List[ActionClass]
    composite_score:      float          # internal, 0–10
    confidence_score:     float          # 0–1
    coverage_score:       float          # 0–1
    observability_status: str
    fired_rules:          List[FiredRule]
    suppressed_rules:     List[FiredRule]
    structural:           StructuralAnalysisResult
    signal:               SignalAnalysisResult
    area_criticality:     str            # safety_criticality value of worst affected region

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_state":       self.decision_state.value,
            "recommended_actions":  [a.value for a in self.recommended_actions],
            "composite_score":      round(self.composite_score, 4),
            "confidence_score":     round(self.confidence_score, 4),
            "coverage_score":       round(self.coverage_score, 4),
            "observability_status": self.observability_status,
            "area_criticality":     self.area_criticality,
            "fired_rules":          [
                {"rule_id": r.rule_id, "description": r.description, "result": r.result.value}
                for r in self.fired_rules
            ],
            "suppressed_rules":     [
                {"rule_id": r.rule_id, "description": r.description, "suppressed_by": "context"}
                for r in self.suppressed_rules
            ],
            "structural": self.structural.to_dict(),
            "signal":     self.signal.to_dict(),
        }


# ---------------------------------------------------------------------------
# Fusion engine
# ---------------------------------------------------------------------------

class FusionEngine:
    """
    Combines structural and signal results under named rules to produce
    a named OperationalState and a recommended ActionClass.
    """

    def __init__(
        self,
        config: Optional[FusionConfig] = None,
        suppression: Optional[SuppressionContext] = None,
    ):
        self.config     = config or FusionConfig()
        self.suppression = suppression or SuppressionContext()

    def fuse(
        self,
        structural: StructuralAnalysisResult,
        signal: SignalAnalysisResult,
        coverage_score: float,
        observability_status: str,
        region_criticality: str = SafetyCriticality.MODERATE.value,
    ) -> FusionResult:
        fired:     List[FiredRule] = []
        suppressed: List[FiredRule] = []

        # --- Step 1: base composite score ---
        crit_mult = self.config.criticality_multiplier.get(region_criticality, 1.0)
        composite = (
            self.config.structural_weight * structural.invariant_score
            + self.config.signal_weight   * signal.rupture_score
        ) * crit_mult
        composite = min(composite, 10.0)

        # --- Step 2: base state from score ---
        base_state = self._score_to_state(composite)

        # --- Step 3: apply hard escalation rules ---
        rule_state, fired, suppressed = self._apply_rules(
            base_state, structural, signal, fired, suppressed
        )

        # --- Step 4: apply observability / coverage logic ---
        final_state = self._apply_coverage_logic(
            rule_state, coverage_score, observability_status
        )

        # --- Step 5: confidence score ---
        confidence = self._compute_confidence(
            structural, signal, coverage_score
        )

        # --- Step 6: recommended actions ---
        actions = self._recommend_actions(
            final_state, structural, signal, observability_status
        )

        return FusionResult(
            decision_state=final_state,
            recommended_actions=actions,
            composite_score=composite,
            confidence_score=confidence,
            coverage_score=coverage_score,
            observability_status=observability_status,
            fired_rules=fired,
            suppressed_rules=suppressed,
            structural=structural,
            signal=signal,
            area_criticality=region_criticality,
        )

    # ------------------------------------------------------------------
    # Score → base state
    # ------------------------------------------------------------------

    def _score_to_state(self, score: float) -> OperationalState:
        if score >= self.config.threshold_critical:
            return OperationalState.STATE_Critical
        if score >= self.config.threshold_high:
            return OperationalState.STATE_HighRisk
        if score >= self.config.threshold_watch:
            return OperationalState.STATE_Watch
        if score >= self.config.threshold_monitor:
            return OperationalState.STATE_Monitor
        return OperationalState.STATE_Normal

    # ------------------------------------------------------------------
    # Hard escalation rules
    # ------------------------------------------------------------------

    def _apply_rules(
        self,
        base: OperationalState,
        structural: StructuralAnalysisResult,
        signal: SignalAnalysisResult,
        fired: List[FiredRule],
        suppressed: List[FiredRule],
    ) -> Tuple[OperationalState, List[FiredRule], List[FiredRule]]:
        current = base
        sj = structural.primary_judgement
        has_rupture = signal.rupture_score > 0.0

        persistent_pressure = any(
            e.event_type == ProcessEventType.PRESSURE_DRIFT
            and e.persistence in (AnomalyPersistence.PERSISTENT, AnomalyPersistence.ESCALATING)
            for e in signal.events
        )
        has_sensor_disagreement = any(
            e.event_type == ProcessEventType.SENSOR_DISAGREEMENT
            for e in signal.events
        )
        has_flow_collapse = any(
            e.event_type == ProcessEventType.FLOW_COLLAPSE
            for e in signal.events
        )

        rules: List[Tuple[str, str, bool, OperationalState]] = [
            # (rule_id, description, condition, target_state)

            # R01: Cycle loss + persistent pressure → at least HighRisk
            (
                "R01",
                "Cycle loss combined with persistent pressure anomaly",
                sj == StructuralJudgement.SJ_CycleLoss and persistent_pressure,
                OperationalState.STATE_HighRisk,
            ),

            # R02: Redundancy loss + sensor disagreement + low coverage
            (
                "R02",
                "Redundancy loss with sensor disagreement — evidence quality uncertain",
                sj == StructuralJudgement.SJ_RedundancyLoss and has_sensor_disagreement,
                OperationalState.STATE_HighRisk,
            ),

            # R03: Partition + rupture signal → Critical
            (
                "R03",
                "Full partition coincides with rupture signal",
                sj == StructuralJudgement.SJ_FullPartition and has_rupture,
                OperationalState.STATE_Critical,
            ),

            # R04: Containment risk → Critical with IsolationReview
            (
                "R04",
                "Containment risk: lost relief paths or unobservable critical region",
                sj == StructuralJudgement.SJ_ContainmentRisk,
                OperationalState.STATE_Critical_IsolationReview,
            ),

            # R05: Coupled escalation risk → OperatorEscalation
            (
                "R05",
                "Coupled escalation risk: multiple critical structural failures co-present",
                sj == StructuralJudgement.SJ_CoupledEscalationRisk,
                OperationalState.STATE_Critical_OperatorEscalation,
            ),

            # R06: Non-closable state → Critical
            (
                "R06",
                "Non-closable state: control dependencies and relief paths simultaneously lost",
                sj == StructuralJudgement.SJ_NonClosableState,
                OperationalState.STATE_Critical,
            ),

            # R07: Control loop instability in safety-critical region + rupture
            (
                "R07",
                "Control loop instability with concurrent rupture signal",
                sj == StructuralJudgement.SJ_ControlLoopInstability and has_rupture,
                OperationalState.STATE_Critical_OperatorEscalation,
            ),

            # R08: Flow collapse + isolation emerging → HighRisk
            (
                "R08",
                "Flow collapse coincides with isolation emerging",
                sj == StructuralJudgement.SJ_IsolationEmerging and has_flow_collapse,
                OperationalState.STATE_HighRisk,
            ),

            # R09: Full partition alone (no rupture) → at least HighRisk
            (
                "R09",
                "Full partition without rupture signal — structural-only escalation",
                sj == StructuralJudgement.SJ_FullPartition and not has_rupture,
                OperationalState.STATE_HighRisk,
            ),

            # R10: Escalating multi-signal anomaly across many components
            (
                "R10",
                "Escalating anomalies across 3+ components — possible propagating failure",
                len([
                    e for e in signal.events
                    if e.persistence == AnomalyPersistence.ESCALATING
                ]) >= 2,
                OperationalState.STATE_HighRisk,
            ),
        ]

        for rule_id, description, condition, target in rules:
            rule = FiredRule(
                rule_id=rule_id,
                description=description,
                result=target,
            )
            if not condition:
                continue
            if self._is_suppressed(rule_id, structural, signal):
                rule.suppressed = True
                suppressed.append(rule)
            else:
                fired.append(rule)
                current = max_state(current, target)

        return current, fired, suppressed

    def _is_suppressed(
        self,
        rule_id: str,
        structural: StructuralAnalysisResult,
        signal: SignalAnalysisResult,
    ) -> bool:
        ctx = self.suppression

        # During declared shutdown, suppress isolation-related rules
        if ctx.declared_shutdown and rule_id in ("R04", "R08", "R09"):
            return True

        # During maintenance bypass, downgrade cycle/redundancy rules
        # unless there is a rupture signal
        if ctx.planned_maintenance and rule_id in ("R01", "R02") and signal.rupture_score == 0.0:
            return True

        # If authorised isolation is declared for the affected components,
        # suppress isolation-emerging escalations
        if ctx.authorised_isolation and rule_id in ("R08",):
            affected = set(structural.affected_components)
            if affected.issubset(set(ctx.authorised_isolation)):
                return True

        return False

    # ------------------------------------------------------------------
    # Coverage / observability logic
    # ------------------------------------------------------------------

    def _apply_coverage_logic(
        self,
        state: OperationalState,
        coverage: float,
        observability: str,
    ) -> OperationalState:
        # Critically under-observed: cannot claim Normal — force Inconclusive
        if observability == "critically_under_observed":
            if state_severity(state) <= state_severity(OperationalState.STATE_Monitor):
                return OperationalState.STATE_Inconclusive

        # Low coverage but not critical: downgrade confident claims
        if coverage < self.config.min_coverage_for_normal:
            if state == OperationalState.STATE_Normal:
                return OperationalState.STATE_Inconclusive

        return state

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        structural: StructuralAnalysisResult,
        signal: SignalAnalysisResult,
        coverage: float,
    ) -> float:
        """
        Confidence reflects how well-supported the decision is.
        Poor coverage, many suppressed rules, or weak evidence all reduce confidence.
        """
        base = coverage                              # starts at coverage fraction
        evidence_bonus = min(len(structural.evidence) * 0.03, 0.15)
        signal_bonus   = min(signal.rupture_score / 10.0 * 0.1, 0.10)
        sensor_disagreement_penalty = -0.10 if any(
            e.event_type == ProcessEventType.SENSOR_DISAGREEMENT
            for e in signal.events
        ) else 0.0
        return max(0.0, min(1.0, base + evidence_bonus + signal_bonus + sensor_disagreement_penalty))

    # ------------------------------------------------------------------
    # Action recommendation
    # ------------------------------------------------------------------

    def _recommend_actions(
        self,
        state: OperationalState,
        structural: StructuralAnalysisResult,
        signal: SignalAnalysisResult,
        observability: str,
    ) -> List[ActionClass]:
        actions: List[ActionClass] = []

        if observability == "critically_under_observed":
            actions.append(ActionClass.DATA_QUALITY_INVESTIGATION)

        sj = structural.primary_judgement

        if state == OperationalState.STATE_Normal:
            actions.append(ActionClass.MONITOR)

        elif state == OperationalState.STATE_Monitor:
            actions.append(ActionClass.MONITOR)

        elif state == OperationalState.STATE_Watch:
            actions.append(ActionClass.INSPECT_LOCAL)

        elif state == OperationalState.STATE_HighRisk:
            if sj in (StructuralJudgement.SJ_RedundancyLoss,
                      StructuralJudgement.SJ_CycleLoss):
                actions.append(ActionClass.INSPECT_CROSS_UNIT)
            else:
                actions.append(ActionClass.OPERATOR_REVIEW)

        elif state == OperationalState.STATE_Critical:
            actions.append(ActionClass.OPERATOR_REVIEW)
            actions.append(ActionClass.ENGINEERING_REVIEW)

        elif state == OperationalState.STATE_Critical_IsolationReview:
            actions.append(ActionClass.ISOLATION_REVIEW)
            actions.append(ActionClass.OPERATOR_REVIEW)

        elif state == OperationalState.STATE_Critical_OperatorEscalation:
            actions.append(ActionClass.OPERATOR_REVIEW)
            actions.append(ActionClass.ENGINEERING_REVIEW)
            if sj in (StructuralJudgement.SJ_FullPartition,
                      StructuralJudgement.SJ_CoupledEscalationRisk):
                actions.append(ActionClass.SHUTDOWN_CONSIDERATION)

        elif state == OperationalState.STATE_Inconclusive:
            actions.append(ActionClass.DATA_QUALITY_INVESTIGATION)

        # Deduplicate while preserving order
        seen: set = set()
        unique: List[ActionClass] = []
        for a in actions:
            if a not in seen:
                seen.add(a)
                unique.append(a)
        return unique
