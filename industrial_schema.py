"""
industrial_schema.py — VeriStrain Scotford
Plant-native entity types, tagged observations, and input validation.
Replaces generic scenario/phase/OHLCV abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ComponentType(str, Enum):
    PUMP            = "Pump"
    COMPRESSOR      = "Compressor"
    VESSEL          = "Vessel"
    HEAT_EXCHANGER  = "HeatExchanger"
    VALVE           = "Valve"
    SENSOR          = "Sensor"
    CONTROL_LOOP    = "ControlLoop"
    REDUNDANCY_LOOP = "RedundancyLoop"
    LINE            = "Line"
    FEED_PATH       = "FeedPath"
    DISCHARGE_PATH  = "DischargePath"
    RECYCLE_PATH    = "RecyclePath"
    UNIT            = "Unit"
    SUBSYSTEM       = "Subsystem"


class OperatingMode(str, Enum):
    STARTUP              = "startup"
    SHUTDOWN             = "shutdown"
    STEADY_STATE         = "steady_state"
    MAINTENANCE_BYPASS   = "maintenance_bypass"
    UPSET_CONDITION      = "upset_condition"
    EMERGENCY_ISOLATION  = "emergency_isolation"
    PARTIAL_LOAD         = "partial_load"
    RECYCLE_MODE         = "recycle_mode"


class SafetyCriticality(str, Enum):
    LOW            = "low_consequence"
    MODERATE       = "moderate_consequence"
    HIGH           = "high_consequence"
    SAFETY_CRITICAL = "safety_critical"


class MeasurementType(str, Enum):
    PRESSURE        = "pressure"
    FLOW            = "flow"
    TEMPERATURE     = "temperature"
    LEVEL           = "level"
    VALVE_STATE     = "valve_state"
    PUMP_STATE      = "pump_state"
    CONTROL_COMMAND = "control_command"
    VIBRATION       = "vibration"
    DENSITY         = "density"
    DIFFERENTIAL_PRESSURE = "differential_pressure"


class DataQuality(str, Enum):
    GOOD        = "good"
    UNCERTAIN   = "uncertain"
    BAD         = "bad"
    SUBSTITUTED = "substituted"
    STALE       = "stale"


class RedundancyClass(str, Enum):
    PRIMARY   = "primary"
    SECONDARY = "secondary"
    TERTIARY  = "tertiary"
    NONE      = "none"


class RunMode(str, Enum):
    DEMO            = "demo"
    SIMULATION      = "simulation"
    SITE_EVALUATION = "site-evaluation"
    PRODUCTION      = "production"


# ---------------------------------------------------------------------------
# Core data objects
# ---------------------------------------------------------------------------

@dataclass
class TaggedObservation:
    """
    A single plant measurement tied to a specific physical sensor and component.
    This is the fundamental input unit — every measurement must be attributable.
    """
    site:             str
    plant_area:       str
    unit_id:          str
    component_id:     str
    component_type:   ComponentType
    sensor_id:        str
    timestamp:        datetime
    measurement_type: MeasurementType
    value:            float
    unit:             str
    quality:          DataQuality
    stream_id:        Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaggedObservation":
        return cls(
            site             = d["site"],
            plant_area       = d["plant_area"],
            unit_id          = d["unit_id"],
            component_id     = d["component_id"],
            component_type   = ComponentType(d["component_type"]),
            sensor_id        = d["sensor_id"],
            timestamp        = _parse_ts(d["timestamp"]),
            measurement_type = MeasurementType(d["measurement_type"]),
            value            = float(d["value"]),
            unit             = d["unit"],
            quality          = DataQuality(d["quality"]),
            stream_id        = d.get("stream_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site":             self.site,
            "plant_area":       self.plant_area,
            "unit_id":          self.unit_id,
            "component_id":     self.component_id,
            "component_type":   self.component_type.value,
            "sensor_id":        self.sensor_id,
            "timestamp":        self.timestamp.isoformat(),
            "measurement_type": self.measurement_type.value,
            "value":            self.value,
            "unit":             self.unit,
            "quality":          self.quality.value,
            "stream_id":        self.stream_id,
        }


@dataclass
class TopologyMetadata:
    """
    Describes the connectivity, operational context, and safety classification
    of a single component within the plant graph.
    """
    component_id:         str
    process_area:         str
    safety_criticality:   SafetyCriticality
    operational_mode:     OperatingMode
    redundancy_class:     RedundancyClass
    nominal_adjacency:    List[str] = field(default_factory=list)
    upstream_component:   Optional[str] = None
    downstream_component: Optional[str] = None
    process_direction:    Optional[str] = None   # "forward" | "reverse" | "bidirectional"
    containment_boundary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id":         self.component_id,
            "process_area":         self.process_area,
            "safety_criticality":   self.safety_criticality.value,
            "operational_mode":     self.operational_mode.value,
            "redundancy_class":     self.redundancy_class.value,
            "nominal_adjacency":    self.nominal_adjacency,
            "upstream_component":   self.upstream_component,
            "downstream_component": self.downstream_component,
            "process_direction":    self.process_direction,
            "containment_boundary": self.containment_boundary,
        }


@dataclass
class PlantObservationBundle:
    """
    A complete, time-bounded bundle of plant observations for one evaluation.
    This is the top-level input object — it replaces the abstract scenario.

    Every field here will be surfaced in the audit output.
    """
    site:              str
    plant_area:        str
    operating_mode:    OperatingMode
    window_start:      datetime
    window_end:        datetime
    run_mode:          RunMode
    observations:      List[TaggedObservation] = field(default_factory=list)
    topology_metadata: List[TopologyMetadata]  = field(default_factory=list)
    data_sources:      List[str]               = field(default_factory=list)

    # ---------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Return a list of validation errors. Empty list means valid."""
        errors: List[str] = []

        if self.run_mode == RunMode.PRODUCTION:
            errors.extend(self._validate_production())
        elif self.run_mode == RunMode.DEMO:
            errors.extend(self._validate_demo_permitted())

        if self.window_start >= self.window_end:
            errors.append("window_start must be before window_end")

        return errors

    def _validate_production(self) -> List[str]:
        errors: List[str] = []
        if not self.observations:
            errors.append("production mode requires at least one observation")
        if not self.data_sources:
            errors.append("production mode requires at least one named data source")
        bad_count = sum(1 for o in self.observations if o.quality == DataQuality.BAD)
        if self.observations and bad_count / len(self.observations) > 0.5:
            errors.append(
                f"more than 50% of observations have BAD quality "
                f"({bad_count}/{len(self.observations)})"
            )
        return errors

    def _validate_demo_permitted(self) -> List[str]:
        # Demo mode is permissive — but flag it clearly.
        return []

    # ---------------------------------------------------------------------------
    # Observability metrics
    # ---------------------------------------------------------------------------

    def coverage_score(self, required_sensors: List[str]) -> float:
        """Fraction of required sensor IDs present in this bundle."""
        if not required_sensors:
            return 1.0
        present: Set[str] = {o.sensor_id for o in self.observations}
        return len(present.intersection(required_sensors)) / len(required_sensors)

    def stale_count(self, threshold_seconds: float = 300.0) -> int:
        """Count observations older than threshold relative to window_end."""
        count = 0
        for o in self.observations:
            age = (self.window_end - o.timestamp).total_seconds()
            if age > threshold_seconds:
                count += 1
        return count

    def bad_quality_count(self) -> int:
        return sum(
            1 for o in self.observations
            if o.quality in (DataQuality.BAD, DataQuality.STALE)
        )

    def sensor_disagreement_pairs(
        self, tolerance: float = 0.05
    ) -> List[tuple[str, str, float]]:
        """
        Find pairs of sensors measuring the same thing on the same component
        whose values diverge by more than `tolerance` (fractional).
        Returns list of (sensor_a, sensor_b, divergence_fraction).
        """
        pairs: List[tuple[str, str, float]] = []
        by_key: Dict[tuple, List[TaggedObservation]] = {}
        for o in self.observations:
            key = (o.component_id, o.measurement_type)
            by_key.setdefault(key, []).append(o)
        for obs_list in by_key.values():
            if len(obs_list) < 2:
                continue
            # Only compare observations from distinct sensors
            by_sensor: Dict[str, List[TaggedObservation]] = {}
            for o in obs_list:
                by_sensor.setdefault(o.sensor_id, []).append(o)
            sensor_ids = list(by_sensor.keys())
            if len(sensor_ids) < 2:
                continue
            for i in range(len(sensor_ids)):
                for j in range(i + 1, len(sensor_ids)):
                    sid_a, sid_b = sensor_ids[i], sensor_ids[j]
                    val_a = sum(o.value for o in by_sensor[sid_a]) / len(by_sensor[sid_a])
                    val_b = sum(o.value for o in by_sensor[sid_b]) / len(by_sensor[sid_b])
                    ref = (abs(val_a) + abs(val_b)) / 2.0
                    if ref == 0:
                        continue
                    div = abs(val_a - val_b) / ref
                    if div > tolerance:
                        pairs.append((sid_a, sid_b, div))
        return pairs

    def observability_status(
        self,
        required_sensors: List[str],
        critical_threshold: float = 0.70,
        partial_threshold: float = 0.90,
    ) -> str:
        """
        Returns 'fully_observable', 'partially_observable', or
        'critically_under_observed'.
        """
        score = self.coverage_score(required_sensors)
        if score >= partial_threshold:
            return "fully_observable"
        if score >= critical_threshold:
            return "partially_observable"
        return "critically_under_observed"

    def to_provenance_dict(self) -> Dict[str, Any]:
        return {
            "site":           self.site,
            "plant_area":     self.plant_area,
            "operating_mode": self.operating_mode.value,
            "run_mode":       self.run_mode.value,
            "window_start":   self.window_start.isoformat(),
            "window_end":     self.window_end.isoformat(),
            "data_sources":   self.data_sources,
            "observation_count": len(self.observations),
            "bad_quality_count": self.bad_quality_count(),
            "stale_count":    self.stale_count(),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(s: str) -> datetime:
    """Parse ISO-8601 timestamp, attaching UTC if no tzinfo present."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
