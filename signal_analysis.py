"""
signal_analysis.py — VeriStrain Scotford
Typed process event detection, persistence tracking, and multi-signal correlation.

Replaces the generic rupture score with plant-meaningful event classifications
and tracks their persistence to distinguish transient noise from developing hazards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from industrial_schema import (
    MeasurementType,
    PlantObservationBundle,
    TaggedObservation,
)


# ---------------------------------------------------------------------------
# Process event types
# ---------------------------------------------------------------------------

class ProcessEventType(str, Enum):
    PRESSURE_SPIKE            = "pressure_spike"
    PRESSURE_DRIFT            = "pressure_drift"
    FLOW_COLLAPSE             = "flow_collapse"
    UNSTABLE_OSCILLATION      = "unstable_oscillation"
    SENSOR_DISAGREEMENT       = "sensor_disagreement"
    PERSISTENT_DIVERGENCE     = "persistent_divergence"
    DELAYED_RECOVERY          = "delayed_recovery"
    THERMAL_IMBALANCE         = "thermal_imbalance"
    PUMP_VALVE_TRANSITION     = "pump_valve_transition_anomaly"
    LOSS_OF_EXPECTED_CORRELATION = "loss_of_expected_correlation"
    CONTROL_RESPONSE_ABSENT   = "control_response_absent"


class AnomalyPersistence(str, Enum):
    TRANSIENT   = "transient"
    REPEATED    = "repeated"
    PERSISTENT  = "persistent"
    ESCALATING  = "escalating"
    SYNCHRONISED = "synchronised"   # across multiple components


# ---------------------------------------------------------------------------
# Event data objects
# ---------------------------------------------------------------------------

@dataclass
class ProcessEvent:
    """
    A typed, attributed process anomaly event derived from plant observations.
    """
    event_type:    ProcessEventType
    sensor_ids:    List[str]
    component_ids: List[str]
    timestamp:     datetime
    magnitude:     float          # dimensionless severity (0.0–1.0 normalised)
    persistence:   AnomalyPersistence
    evidence:      List[str]      # human-readable evidence strings
    region:        Optional[str] = None
    raw_values:    Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type":    self.event_type.value,
            "sensor_ids":    self.sensor_ids,
            "component_ids": self.component_ids,
            "timestamp":     self.timestamp.isoformat(),
            "magnitude":     round(self.magnitude, 4),
            "persistence":   self.persistence.value,
            "evidence":      self.evidence,
            "region":        self.region,
            "raw_values":    {k: round(v, 4) for k, v in self.raw_values.items()},
        }


@dataclass
class SignalAnalysisResult:
    """Output of the signal analysis layer for one observation bundle."""
    events:           List[ProcessEvent]
    rupture_score:    float          # 0.0–10.0, for fusion
    dominant_event:   Optional[ProcessEventType]
    multi_signal_alerts: List[str]   # cross-signal correlation findings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rupture_score":     round(self.rupture_score, 4),
            "event_count":       len(self.events),
            "dominant_event":    self.dominant_event.value if self.dominant_event else None,
            "events":            [e.to_dict() for e in self.events],
            "multi_signal_alerts": self.multi_signal_alerts,
        }


# ---------------------------------------------------------------------------
# Thresholds (overridable by site profile)
# ---------------------------------------------------------------------------

@dataclass
class SignalThresholds:
    pressure_spike_fraction:   float = 0.10   # 10% above rolling mean
    pressure_drift_window_s:   float = 600.0  # 10-minute drift window
    flow_collapse_fraction:    float = 0.25   # 25% drop from expected
    oscillation_zero_crossings: int  = 4      # min zero-crossings in window
    sensor_disagreement_frac:  float = 0.05   # 5% relative divergence
    persistent_event_min_count: int  = 3      # events to become "persistent"
    escalating_gradient:       float = 0.10   # magnitude growth per event


# ---------------------------------------------------------------------------
# Signal analyser
# ---------------------------------------------------------------------------

class SignalAnalyser:
    """
    Detects typed process anomalies from a PlantObservationBundle.
    Does not depend on the topology model — produces events that the
    fusion engine will combine with structural judgements.
    """

    def __init__(self, thresholds: Optional[SignalThresholds] = None):
        self.thresholds = thresholds or SignalThresholds()

    def analyse(self, bundle: PlantObservationBundle) -> SignalAnalysisResult:
        events: List[ProcessEvent] = []

        events.extend(self._detect_sensor_disagreement(bundle))
        events.extend(self._detect_pressure_events(bundle))
        events.extend(self._detect_flow_collapse(bundle))
        events.extend(self._detect_oscillation(bundle))
        events.extend(self._detect_control_response_absent(bundle))

        events = self._apply_persistence(events)
        multi_alerts = self._correlate_multi_signal(events, bundle)
        score = self._compute_rupture_score(events)
        dominant = self._dominant_event(events)

        return SignalAnalysisResult(
            events=events,
            rupture_score=score,
            dominant_event=dominant,
            multi_signal_alerts=multi_alerts,
        )

    # ------------------------------------------------------------------
    # Individual detectors
    # ------------------------------------------------------------------

    def _detect_sensor_disagreement(
        self, bundle: PlantObservationBundle
    ) -> List[ProcessEvent]:
        events: List[ProcessEvent] = []
        pairs = bundle.sensor_disagreement_pairs(
            tolerance=self.thresholds.sensor_disagreement_frac
        )
        for sensor_a, sensor_b, divergence in pairs:
            # Find the components involved
            comp_a = next(
                (o.component_id for o in bundle.observations if o.sensor_id == sensor_a),
                sensor_a,
            )
            comp_b = next(
                (o.component_id for o in bundle.observations if o.sensor_id == sensor_b),
                sensor_b,
            )
            events.append(ProcessEvent(
                event_type=ProcessEventType.SENSOR_DISAGREEMENT,
                sensor_ids=[sensor_a, sensor_b],
                component_ids=list({comp_a, comp_b}),
                timestamp=bundle.window_end,
                magnitude=min(divergence, 1.0),
                persistence=AnomalyPersistence.TRANSIENT,
                evidence=[
                    f"Sensors {sensor_a} and {sensor_b} diverge by "
                    f"{divergence:.1%} on component(s) {comp_a}/{comp_b}"
                ],
                raw_values={"divergence_fraction": divergence},
            ))
        return events

    def _detect_pressure_events(
        self, bundle: PlantObservationBundle
    ) -> List[ProcessEvent]:
        events: List[ProcessEvent] = []
        pressure_obs = [
            o for o in bundle.observations
            if o.measurement_type in (
                MeasurementType.PRESSURE,
                MeasurementType.DIFFERENTIAL_PRESSURE,
            )
        ]

        # Group by component
        by_component: Dict[str, List[TaggedObservation]] = {}
        for o in pressure_obs:
            by_component.setdefault(o.component_id, []).append(o)

        for comp_id, obs_list in by_component.items():
            if len(obs_list) < 2:
                continue
            obs_sorted = sorted(obs_list, key=lambda x: x.timestamp)
            values = [o.value for o in obs_sorted]
            mean_val = sum(values) / len(values)
            if mean_val == 0:
                continue

            # Spike: max value exceeds mean by spike threshold
            max_val = max(values)
            spike_frac = (max_val - mean_val) / abs(mean_val)
            if spike_frac > self.thresholds.pressure_spike_fraction:
                events.append(ProcessEvent(
                    event_type=ProcessEventType.PRESSURE_SPIKE,
                    sensor_ids=[o.sensor_id for o in obs_sorted],
                    component_ids=[comp_id],
                    timestamp=obs_sorted[-1].timestamp,
                    magnitude=min(spike_frac, 1.0),
                    persistence=AnomalyPersistence.TRANSIENT,
                    evidence=[
                        f"Pressure spike on {comp_id}: "
                        f"{max_val:.1f} vs mean {mean_val:.1f} "
                        f"({spike_frac:.1%} above mean)"
                    ],
                    raw_values={"peak": max_val, "mean": mean_val,
                                "spike_fraction": spike_frac},
                ))

            # Drift: monotone trend over the window
            if len(values) >= 3:
                drift = values[-1] - values[0]
                drift_frac = drift / abs(mean_val) if mean_val != 0 else 0.0
                monotone = all(
                    values[i] <= values[i + 1] for i in range(len(values) - 1)
                ) or all(
                    values[i] >= values[i + 1] for i in range(len(values) - 1)
                )
                if monotone and abs(drift_frac) > self.thresholds.pressure_spike_fraction:
                    events.append(ProcessEvent(
                        event_type=ProcessEventType.PRESSURE_DRIFT,
                        sensor_ids=[o.sensor_id for o in obs_sorted],
                        component_ids=[comp_id],
                        timestamp=obs_sorted[-1].timestamp,
                        magnitude=min(abs(drift_frac), 1.0),
                        persistence=AnomalyPersistence.TRANSIENT,
                        evidence=[
                            f"Monotone pressure drift on {comp_id}: "
                            f"{values[0]:.1f} → {values[-1]:.1f} "
                            f"({drift_frac:+.1%} over window)"
                        ],
                        raw_values={"start": values[0], "end": values[-1],
                                    "drift_fraction": drift_frac},
                    ))
        return events

    def _detect_flow_collapse(
        self, bundle: PlantObservationBundle
    ) -> List[ProcessEvent]:
        events: List[ProcessEvent] = []
        flow_obs = [
            o for o in bundle.observations
            if o.measurement_type == MeasurementType.FLOW
        ]
        by_component: Dict[str, List[TaggedObservation]] = {}
        for o in flow_obs:
            by_component.setdefault(o.component_id, []).append(o)

        for comp_id, obs_list in by_component.items():
            if len(obs_list) < 2:
                continue
            values = [o.value for o in sorted(obs_list, key=lambda x: x.timestamp)]
            if values[0] == 0:
                continue
            drop = (values[0] - values[-1]) / abs(values[0])
            if drop > self.thresholds.flow_collapse_fraction:
                events.append(ProcessEvent(
                    event_type=ProcessEventType.FLOW_COLLAPSE,
                    sensor_ids=[o.sensor_id for o in obs_list],
                    component_ids=[comp_id],
                    timestamp=obs_list[-1].timestamp,
                    magnitude=min(drop, 1.0),
                    persistence=AnomalyPersistence.TRANSIENT,
                    evidence=[
                        f"Flow collapse on {comp_id}: "
                        f"{values[0]:.1f} → {values[-1]:.1f} "
                        f"({drop:.1%} reduction)"
                    ],
                    raw_values={"initial": values[0], "final": values[-1],
                                "drop_fraction": drop},
                ))
        return events

    def _detect_oscillation(
        self, bundle: PlantObservationBundle
    ) -> List[ProcessEvent]:
        events: List[ProcessEvent] = []
        for mtype in (MeasurementType.PRESSURE, MeasurementType.FLOW):
            obs = [o for o in bundle.observations if o.measurement_type == mtype]
            by_component: Dict[str, List[TaggedObservation]] = {}
            for o in obs:
                by_component.setdefault(o.component_id, []).append(o)
            for comp_id, obs_list in by_component.items():
                if len(obs_list) < 4:
                    continue
                values = [
                    o.value
                    for o in sorted(obs_list, key=lambda x: x.timestamp)
                ]
                mean_val = sum(values) / len(values)
                centred = [v - mean_val for v in values]
                crossings = sum(
                    1
                    for i in range(len(centred) - 1)
                    if centred[i] * centred[i + 1] < 0
                )
                if crossings >= self.thresholds.oscillation_zero_crossings:
                    mag = (max(values) - min(values)) / (abs(mean_val) + 1e-9)
                    events.append(ProcessEvent(
                        event_type=ProcessEventType.UNSTABLE_OSCILLATION,
                        sensor_ids=[o.sensor_id for o in obs_list],
                        component_ids=[comp_id],
                        timestamp=obs_list[-1].timestamp,
                        magnitude=min(mag, 1.0),
                        persistence=AnomalyPersistence.TRANSIENT,
                        evidence=[
                            f"Unstable oscillation on {comp_id} "
                            f"({mtype.value}): {crossings} zero-crossings, "
                            f"amplitude {mag:.2f}×mean"
                        ],
                        raw_values={"zero_crossings": crossings, "amplitude_ratio": mag},
                    ))
        return events

    def _detect_control_response_absent(
        self, bundle: PlantObservationBundle
    ) -> List[ProcessEvent]:
        """
        Detect: control command changed but expected downstream effect absent.
        Requires both CONTROL_COMMAND and at least one PRESSURE/FLOW observation
        on the same component.
        """
        events: List[ProcessEvent] = []
        cmd_obs = [
            o for o in bundle.observations
            if o.measurement_type == MeasurementType.CONTROL_COMMAND
        ]
        for cmd in cmd_obs:
            downstream = [
                o for o in bundle.observations
                if o.component_id == cmd.component_id
                and o.measurement_type in (MeasurementType.PRESSURE, MeasurementType.FLOW)
                and o.timestamp > cmd.timestamp
            ]
            if not downstream:
                events.append(ProcessEvent(
                    event_type=ProcessEventType.CONTROL_RESPONSE_ABSENT,
                    sensor_ids=[cmd.sensor_id],
                    component_ids=[cmd.component_id],
                    timestamp=cmd.timestamp,
                    magnitude=0.6,
                    persistence=AnomalyPersistence.TRANSIENT,
                    evidence=[
                        f"Control command on {cmd.component_id} "
                        f"({cmd.sensor_id}) issued but no downstream "
                        f"pressure/flow response observed in window"
                    ],
                ))
        return events

    # ------------------------------------------------------------------
    # Persistence and correlation
    # ------------------------------------------------------------------

    def _apply_persistence(self, events: List[ProcessEvent]) -> List[ProcessEvent]:
        """
        Group events by type+component and upgrade persistence classification
        based on repetition and magnitude trend.
        """
        from collections import defaultdict
        groups: Dict[Tuple[str, str], List[ProcessEvent]] = defaultdict(list)
        for e in events:
            key = (e.event_type.value, ",".join(sorted(e.component_ids)))
            groups[key].append(e)

        result: List[ProcessEvent] = []
        for key, group in groups.items():
            group_sorted = sorted(group, key=lambda x: x.timestamp)
            n = len(group_sorted)
            if n >= self.thresholds.persistent_event_min_count:
                magnitudes = [e.magnitude for e in group_sorted]
                escalating = all(
                    magnitudes[i + 1] >= magnitudes[i] * (1 + self.thresholds.escalating_gradient)
                    for i in range(len(magnitudes) - 1)
                )
                persistence = (
                    AnomalyPersistence.ESCALATING if escalating
                    else AnomalyPersistence.PERSISTENT
                )
            elif n >= 2:
                persistence = AnomalyPersistence.REPEATED
            else:
                persistence = AnomalyPersistence.TRANSIENT

            for e in group_sorted:
                result.append(ProcessEvent(
                    event_type=e.event_type,
                    sensor_ids=e.sensor_ids,
                    component_ids=e.component_ids,
                    timestamp=e.timestamp,
                    magnitude=e.magnitude,
                    persistence=persistence,
                    evidence=e.evidence,
                    region=e.region,
                    raw_values=e.raw_values,
                ))
        return result

    def _correlate_multi_signal(
        self, events: List[ProcessEvent], bundle: PlantObservationBundle
    ) -> List[str]:
        alerts: List[str] = []

        # Check: pressure drift without flow adaptation
        pressure_drifts = [
            e for e in events if e.event_type == ProcessEventType.PRESSURE_DRIFT
        ]
        flow_collapses = [
            e for e in events if e.event_type == ProcessEventType.FLOW_COLLAPSE
        ]
        for pd in pressure_drifts:
            related_flow = [
                fc for fc in flow_collapses
                if set(pd.component_ids).intersection(fc.component_ids)
            ]
            if not related_flow:
                alerts.append(
                    f"Pressure drift on {pd.component_ids} occurred "
                    f"without corresponding flow adaptation"
                )

        # Check: sensor disagreement across a shared boundary
        disagreements = [
            e for e in events if e.event_type == ProcessEventType.SENSOR_DISAGREEMENT
        ]
        if len(disagreements) >= 2:
            all_sensors = [s for e in disagreements for s in e.sensor_ids]
            alerts.append(
                f"Multiple sensor disagreement events across "
                f"{len(set(all_sensors))} sensors — possible measurement boundary failure"
            )

        # Check: synchronised anomalies across components
        persistent = [
            e for e in events
            if e.persistence in (AnomalyPersistence.PERSISTENT, AnomalyPersistence.ESCALATING)
        ]
        affected_components: Set[str] = set()
        for e in persistent:
            affected_components.update(e.component_ids)
        if len(affected_components) >= 3:
            alerts.append(
                f"Persistent anomalies detected across {len(affected_components)} "
                f"components simultaneously — possible coupled or propagating failure"
            )

        # Check: control response absent alongside pressure spike
        ctrl_absent = [
            e for e in events if e.event_type == ProcessEventType.CONTROL_RESPONSE_ABSENT
        ]
        pressure_spikes = [
            e for e in events if e.event_type == ProcessEventType.PRESSURE_SPIKE
        ]
        for ca in ctrl_absent:
            for ps in pressure_spikes:
                if set(ca.component_ids).intersection(ps.component_ids):
                    alerts.append(
                        f"Control response absent on {ca.component_ids} "
                        f"coincides with pressure spike — possible closed-loop breakdown"
                    )

        return alerts

    # ------------------------------------------------------------------
    # Score and summary
    # ------------------------------------------------------------------

    def _compute_rupture_score(self, events: List[ProcessEvent]) -> float:
        """
        Map events to a 0–10 rupture score for fusion.
        Persistence multipliers weight serious events more heavily.
        """
        persistence_weight = {
            AnomalyPersistence.TRANSIENT:    0.5,
            AnomalyPersistence.REPEATED:     1.0,
            AnomalyPersistence.PERSISTENT:   2.0,
            AnomalyPersistence.ESCALATING:   3.5,
            AnomalyPersistence.SYNCHRONISED: 4.0,
        }
        severity_base = {
            ProcessEventType.PRESSURE_SPIKE:              1.5,
            ProcessEventType.PRESSURE_DRIFT:              1.2,
            ProcessEventType.FLOW_COLLAPSE:               1.8,
            ProcessEventType.UNSTABLE_OSCILLATION:        1.3,
            ProcessEventType.SENSOR_DISAGREEMENT:         1.0,
            ProcessEventType.PERSISTENT_DIVERGENCE:       2.0,
            ProcessEventType.DELAYED_RECOVERY:            1.0,
            ProcessEventType.THERMAL_IMBALANCE:           1.2,
            ProcessEventType.PUMP_VALVE_TRANSITION:       0.8,
            ProcessEventType.LOSS_OF_EXPECTED_CORRELATION: 1.5,
            ProcessEventType.CONTROL_RESPONSE_ABSENT:     2.0,
        }
        score = 0.0
        for e in events:
            base = severity_base.get(e.event_type, 1.0)
            pw   = persistence_weight.get(e.persistence, 1.0)
            score += base * pw * e.magnitude
        return min(score, 10.0)

    def _dominant_event(
        self, events: List[ProcessEvent]
    ) -> Optional[ProcessEventType]:
        if not events:
            return None
        return max(events, key=lambda e: e.magnitude).event_type
