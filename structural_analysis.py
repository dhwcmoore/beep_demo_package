"""
structural_analysis.py — VeriStrain Scotford
Enriched structural judgement taxonomy derived from physical/functional topology comparison.

Extends the original three-value classifier (NoBreak / CycleLoss / Partition)
into a Scotford-facing vocabulary that expresses process-meaningful distinctions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from topology_model import EdgeType, PlantEdge, PlantRegion, TopologyComparison


# ---------------------------------------------------------------------------
# Structural judgement taxonomy
# ---------------------------------------------------------------------------

class StructuralJudgement(str, Enum):
    SJ_Normal                   = "SJ_Normal"
    SJ_CycleLoss                = "SJ_CycleLoss"
    SJ_RedundancyLoss           = "SJ_RedundancyLoss"
    SJ_IsolationEmerging        = "SJ_IsolationEmerging"
    SJ_PartialPartition         = "SJ_PartialPartition"
    SJ_FullPartition            = "SJ_FullPartition"
    SJ_PathMismatch             = "SJ_PathMismatch"
    SJ_FlowStorageContradiction = "SJ_FlowStorageContradiction"
    SJ_ControlLoopInstability   = "SJ_ControlLoopInstability"
    SJ_NonClosableState         = "SJ_NonClosableState"
    SJ_ContainmentRisk          = "SJ_ContainmentRisk"
    SJ_CoupledEscalationRisk    = "SJ_CoupledEscalationRisk"


# Severity ordering for the judgement types (higher = worse)
_SJ_SEVERITY: Dict[StructuralJudgement, int] = {
    StructuralJudgement.SJ_Normal:                   0,
    StructuralJudgement.SJ_CycleLoss:               2,
    StructuralJudgement.SJ_RedundancyLoss:          3,
    StructuralJudgement.SJ_IsolationEmerging:       3,
    StructuralJudgement.SJ_PathMismatch:            3,
    StructuralJudgement.SJ_FlowStorageContradiction: 4,
    StructuralJudgement.SJ_ControlLoopInstability:  4,
    StructuralJudgement.SJ_PartialPartition:        5,
    StructuralJudgement.SJ_NonClosableState:        5,
    StructuralJudgement.SJ_ContainmentRisk:         6,
    StructuralJudgement.SJ_FullPartition:           6,
    StructuralJudgement.SJ_CoupledEscalationRisk:   7,
}


def sj_severity(sj: StructuralJudgement) -> int:
    return _SJ_SEVERITY.get(sj, 0)


# ---------------------------------------------------------------------------
# Structural analysis result
# ---------------------------------------------------------------------------

@dataclass
class StructuralAnalysisResult:
    """
    Full structural assessment from the topology comparison.
    The primary judgement is the highest-severity condition found.
    Additional judgements capture secondary conditions that co-exist.
    """
    primary_judgement:     StructuralJudgement
    secondary_judgements:  List[StructuralJudgement]
    affected_regions:      List[str]
    affected_components:   List[str]
    evidence:              List[str]
    invariant_score:       float           # 0.0–10.0 for fusion
    physical_b0:           int
    physical_b1:           int
    functional_b0:         int
    functional_b1:         int

    # Typed edge losses surfaced directly
    lost_material_paths:       List[PlantEdge] = field(default_factory=list)
    lost_control_dependencies: List[PlantEdge] = field(default_factory=list)
    lost_relief_paths:         List[PlantEdge] = field(default_factory=list)
    disconnected_regions:      List[str]       = field(default_factory=list)
    unobservable_regions:      List[str]       = field(default_factory=list)

    @property
    def structural_break(self) -> bool:
        return self.primary_judgement != StructuralJudgement.SJ_Normal

    @property
    def all_judgements(self) -> List[StructuralJudgement]:
        return [self.primary_judgement] + self.secondary_judgements

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_judgement":    self.primary_judgement.value,
            "secondary_judgements": [sj.value for sj in self.secondary_judgements],
            "affected_regions":     self.affected_regions,
            "affected_components":  self.affected_components,
            "evidence":             self.evidence,
            "invariant_score":      round(self.invariant_score, 4),
            "betti": {
                "physical_b0":   self.physical_b0,
                "physical_b1":   self.physical_b1,
                "functional_b0": self.functional_b0,
                "functional_b1": self.functional_b1,
            },
            "lost_material_paths": [
                {"source": e.source, "target": e.target, "stream_id": e.stream_id}
                for e in self.lost_material_paths
            ],
            "lost_control_dependencies": [
                {"source": e.source, "target": e.target}
                for e in self.lost_control_dependencies
            ],
            "lost_relief_paths": [
                {"source": e.source, "target": e.target}
                for e in self.lost_relief_paths
            ],
            "disconnected_regions":  self.disconnected_regions,
            "unobservable_regions":  self.unobservable_regions,
        }


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class StructuralAnalyser:
    """
    Classifies TopologyComparison results into the Scotford structural
    judgement vocabulary.

    Classification precedence (highest severity wins as primary):
      CoupledEscalationRisk > ContainmentRisk = FullPartition >
      NonClosableState = PartialPartition > ControlLoopInstability =
      FlowStorageContradiction > PathMismatch = IsolationEmerging =
      RedundancyLoss > CycleLoss > Normal
    """

    def classify(
        self,
        comparison: TopologyComparison,
        critical_regions: Optional[List[PlantRegion]] = None,
    ) -> StructuralAnalysisResult:
        critical_regions = critical_regions or []
        judgements: List[StructuralJudgement] = []
        evidence: List[str] = []
        affected_regions: List[str] = []
        affected_components: List[str] = []

        # --- Full partition ---
        if comparison.partition_emerged:
            judgements.append(StructuralJudgement.SJ_FullPartition)
            evidence.append(
                f"Plant graph split into {comparison.functional_b0} components "
                f"(was {comparison.physical_b0})"
            )
            affected_regions.extend(comparison.disconnected_regions)

        # --- Partial partition: disconnected regions even without full graph split ---
        elif comparison.disconnected_regions:
            judgements.append(StructuralJudgement.SJ_PartialPartition)
            evidence.append(
                f"Regions internally disconnected: "
                f"{', '.join(comparison.disconnected_regions)}"
            )
            affected_regions.extend(comparison.disconnected_regions)

        # --- Redundancy loss ---
        if comparison.redundancy_lost:
            judgements.append(StructuralJudgement.SJ_RedundancyLoss)
            evidence.append(
                "Physical redundancy present (cycle in physical graph) "
                "but functional redundancy lost (no cycle in functional graph)"
            )
            for e in comparison.lost_redundancy_relations:
                affected_components.extend([e.source, e.target])

        # --- Cycle loss without full redundancy loss (cycle count reduced but not zero) ---
        elif comparison.cycle_lost and not comparison.redundancy_lost:
            judgements.append(StructuralJudgement.SJ_CycleLoss)
            evidence.append(
                f"Cycle count reduced: physical b1={comparison.physical_b1}, "
                f"functional b1={comparison.functional_b1}"
            )

        # --- Isolation emerging: material paths lost but no partition yet ---
        if comparison.lost_material_paths and not comparison.partition_emerged:
            judgements.append(StructuralJudgement.SJ_IsolationEmerging)
            for e in comparison.lost_material_paths:
                evidence.append(
                    f"Material flow path {e.source}→{e.target} inactive"
                    + (f" (stream: {e.stream_id})" if e.stream_id else "")
                )
                affected_components.extend([e.source, e.target])

        # --- Path mismatch: lost material paths in different directions ---
        if (
            comparison.lost_material_paths
            and len({(e.source, e.target) for e in comparison.lost_material_paths}) >= 2
        ):
            judgements.append(StructuralJudgement.SJ_PathMismatch)
            evidence.append(
                f"Multiple material flow paths lost in different directions "
                f"({len(comparison.lost_material_paths)} paths)"
            )

        # --- Control loop instability: control dependency edges lost ---
        if comparison.lost_control_dependencies:
            judgements.append(StructuralJudgement.SJ_ControlLoopInstability)
            for e in comparison.lost_control_dependencies:
                evidence.append(
                    f"Control dependency {e.source}→{e.target} broken"
                )
                affected_components.extend([e.source, e.target])

        # --- Containment risk: unobservable regions or lost relief paths in critical areas ---
        containment_triggered = False
        if comparison.unobservable_regions:
            critical_unobservable = [
                r.region_id for r in critical_regions
                if r.region_id in comparison.unobservable_regions
            ]
            if critical_unobservable:
                judgements.append(StructuralJudgement.SJ_ContainmentRisk)
                evidence.append(
                    f"Critical regions without measurement observability: "
                    f"{', '.join(critical_unobservable)}"
                )
                affected_regions.extend(critical_unobservable)
                containment_triggered = True

        if comparison.lost_relief_paths:
            judgements.append(StructuralJudgement.SJ_ContainmentRisk)
            for e in comparison.lost_relief_paths:
                evidence.append(
                    f"Relief path {e.source}→{e.target} inactive — "
                    f"containment boundary may be compromised"
                )
                affected_components.extend([e.source, e.target])
            containment_triggered = True

        # --- Non-closable state: control dependencies broken in a region without relief ---
        if comparison.lost_control_dependencies and comparison.lost_relief_paths:
            judgements.append(StructuralJudgement.SJ_NonClosableState)
            evidence.append(
                "Control dependencies and relief paths simultaneously inactive — "
                "system may be in a non-closable state"
            )

        # --- Coupled escalation risk: partition + control loss, or
        #     multiple critical regions simultaneously affected ---
        critical_region_ids = {r.region_id for r in critical_regions}
        critical_affected = [r for r in affected_regions if r in critical_region_ids]
        if (
            comparison.partition_emerged and comparison.lost_control_dependencies
        ) or len(critical_affected) >= 2:
            judgements.append(StructuralJudgement.SJ_CoupledEscalationRisk)
            evidence.append(
                "Multiple critical structural failures co-present — "
                "coupled escalation risk"
            )

        # --- Flow/storage contradiction: flow active but containment path broken ---
        if (
            not comparison.lost_material_paths
            and comparison.lost_relief_paths
            and not comparison.partition_emerged
        ):
            judgements.append(StructuralJudgement.SJ_FlowStorageContradiction)
            evidence.append(
                "Material flow paths intact but relief paths inactive — "
                "flow/containment contradiction"
            )

        if not judgements:
            judgements.append(StructuralJudgement.SJ_Normal)
            evidence.append("Physical and functional topology consistent — no structural break")

        # Select primary (highest severity)
        primary = max(judgements, key=sj_severity)
        secondary = [sj for sj in judgements if sj != primary]

        # Compute invariant score
        score = self._compute_score(primary, secondary, comparison)

        return StructuralAnalysisResult(
            primary_judgement=primary,
            secondary_judgements=secondary,
            affected_regions=list(dict.fromkeys(affected_regions)),   # dedup, preserve order
            affected_components=list(dict.fromkeys(affected_components)),
            evidence=evidence,
            invariant_score=score,
            physical_b0=comparison.physical_b0,
            physical_b1=comparison.physical_b1,
            functional_b0=comparison.functional_b0,
            functional_b1=comparison.functional_b1,
            lost_material_paths=comparison.lost_material_paths,
            lost_control_dependencies=comparison.lost_control_dependencies,
            lost_relief_paths=comparison.lost_relief_paths,
            disconnected_regions=comparison.disconnected_regions,
            unobservable_regions=comparison.unobservable_regions,
        )

    def _compute_score(
        self,
        primary: StructuralJudgement,
        secondary: List[StructuralJudgement],
        comparison: TopologyComparison,
    ) -> float:
        """Map structural judgements to 0–10 invariant score."""
        base_scores: Dict[StructuralJudgement, float] = {
            StructuralJudgement.SJ_Normal:                   0.0,
            StructuralJudgement.SJ_CycleLoss:               3.0,
            StructuralJudgement.SJ_RedundancyLoss:          4.0,
            StructuralJudgement.SJ_IsolationEmerging:       3.5,
            StructuralJudgement.SJ_PartialPartition:        5.0,
            StructuralJudgement.SJ_PathMismatch:            3.0,
            StructuralJudgement.SJ_FlowStorageContradiction: 4.5,
            StructuralJudgement.SJ_ControlLoopInstability:  4.0,
            StructuralJudgement.SJ_NonClosableState:        6.0,
            StructuralJudgement.SJ_ContainmentRisk:         6.5,
            StructuralJudgement.SJ_FullPartition:           7.0,
            StructuralJudgement.SJ_CoupledEscalationRisk:   9.0,
        }
        score = base_scores.get(primary, 0.0)
        # Secondary conditions add a fraction of their base
        for sj in secondary:
            score += base_scores.get(sj, 0.0) * 0.2
        # Bonus for multiple inactive edge types
        inactive_types = sum([
            bool(comparison.lost_material_paths),
            bool(comparison.lost_control_dependencies),
            bool(comparison.lost_relief_paths),
            bool(comparison.lost_redundancy_relations),
        ])
        score += (inactive_types - 1) * 0.5 if inactive_types > 1 else 0.0
        return min(score, 10.0)
