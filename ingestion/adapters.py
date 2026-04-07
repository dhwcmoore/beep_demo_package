"""
ingestion/adapters.py — VeriStrain Scotford
Data ingestion adapters for real plant data formats.

Supports:
  - CSV historian exports (with tag/timestamp/value columns)
  - JSON tag-value streams
  - Structured event logs
  - Process snapshots (one value per tag at a fixed timestamp)

All adapters produce TaggedObservation objects for the pipeline.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, Tuple

from industrial_schema import (
    ComponentType,
    DataQuality,
    MeasurementType,
    TaggedObservation,
)
from ingestion.tag_normaliser import TagNormaliser


# ---------------------------------------------------------------------------
# Time alignment configuration
# ---------------------------------------------------------------------------

@dataclass
class TimeAlignmentPolicy:
    """
    Policy for handling time misalignment in multi-source data.
    """
    staleness_threshold_seconds: float = 300.0      # values older than this are STALE
    interpolation_window_seconds: float = 60.0       # window for linear interpolation
    batch_window_seconds: float = 900.0              # 15-minute batch window
    max_clock_skew_seconds: float = 10.0             # allowable clock skew between sources
    drop_future_timestamps: bool = True              # reject values with future timestamps

    def classify_quality(
        self,
        obs_time: datetime,
        reference_time: datetime,
        raw_quality: Optional[str] = None,
    ) -> DataQuality:
        """Determine DataQuality based on time and raw quality flag."""
        if raw_quality and raw_quality.lower() in ("bad", "0", "false"):
            return DataQuality.BAD
        if raw_quality and raw_quality.lower() in ("uncertain", "1"):
            return DataQuality.UNCERTAIN

        age_s = (reference_time - obs_time).total_seconds()
        if self.drop_future_timestamps and age_s < -self.max_clock_skew_seconds:
            return DataQuality.BAD
        if age_s > self.staleness_threshold_seconds:
            return DataQuality.STALE
        if age_s > self.staleness_threshold_seconds * 0.5:
            return DataQuality.UNCERTAIN
        return DataQuality.GOOD


# ---------------------------------------------------------------------------
# Tag-to-component mapping
# ---------------------------------------------------------------------------

@dataclass
class TagComponentMapping:
    """Maps a canonical sensor ID to its plant context."""
    sensor_id:        str
    component_id:     str
    component_type:   ComponentType
    measurement_type: MeasurementType
    unit:             str
    unit_id:          str
    plant_area:       str
    site:             str
    stream_id:        Optional[str] = None


class ComponentRegistry:
    """
    Lookup table from canonical sensor ID → TagComponentMapping.
    Built from site profile data.
    """

    def __init__(self, mappings: List[TagComponentMapping]):
        self._by_sensor: Dict[str, TagComponentMapping] = {
            m.sensor_id: m for m in mappings
        }

    def lookup(self, sensor_id: str) -> Optional[TagComponentMapping]:
        return self._by_sensor.get(sensor_id)

    def all_sensor_ids(self) -> List[str]:
        return list(self._by_sensor.keys())


# ---------------------------------------------------------------------------
# Base adapter interface
# ---------------------------------------------------------------------------

class IngestionError(Exception):
    pass


@dataclass
class IngestionReport:
    """Summary of what was accepted and rejected during ingestion."""
    total_rows:        int = 0
    accepted_rows:     int = 0
    dropped_rows:      int = 0
    unresolved_tags:   List[str] = field(default_factory=list)
    unmapped_sensors:  List[str] = field(default_factory=list)
    quality_warnings:  List[str] = field(default_factory=list)

    @property
    def drop_rate(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return self.dropped_rows / self.total_rows


# ---------------------------------------------------------------------------
# CSV historian adapter
# ---------------------------------------------------------------------------

class CSVHistorianAdapter:
    """
    Reads a CSV file exported from a process historian.

    Expected column layout (configurable):
      timestamp, tag, value, quality
    or wide format:
      timestamp, PT-8801, PT-8802, ...

    Both layouts are auto-detected.
    """

    def __init__(
        self,
        normaliser: TagNormaliser,
        registry: ComponentRegistry,
        time_policy: Optional[TimeAlignmentPolicy] = None,
        # Column name overrides
        timestamp_col: str = "timestamp",
        tag_col:       str = "tag",
        value_col:     str = "value",
        quality_col:   str = "quality",
        site:          str = "Scotford",
    ):
        self.normaliser     = normaliser
        self.registry       = registry
        self.time_policy    = time_policy or TimeAlignmentPolicy()
        self.timestamp_col  = timestamp_col
        self.tag_col        = tag_col
        self.value_col      = value_col
        self.quality_col    = quality_col
        self.site           = site

    def ingest_file(
        self,
        filepath: str,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[List[TaggedObservation], IngestionReport]:
        with open(filepath, newline="", encoding="utf-8") as f:
            content = f.read()
        return self.ingest_text(content, reference_time)

    def ingest_text(
        self,
        csv_text: str,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[List[TaggedObservation], IngestionReport]:
        ref_time = reference_time or datetime.now(timezone.utc)
        reader = csv.DictReader(io.StringIO(csv_text))
        if reader.fieldnames is None:
            raise IngestionError("CSV has no header row")

        fieldnames = [f.strip() for f in reader.fieldnames]
        is_wide = (self.tag_col not in fieldnames)

        observations: List[TaggedObservation] = []
        report = IngestionReport()

        if is_wide:
            rows = list(reader)
            report.total_rows = len(rows)
            for row in rows:
                ts_str = row.get(self.timestamp_col, "").strip()
                if not ts_str:
                    report.dropped_rows += 1
                    continue
                try:
                    ts = _parse_ts(ts_str)
                except ValueError:
                    report.dropped_rows += 1
                    continue
                for col, raw_val in row.items():
                    if col.strip() == self.timestamp_col:
                        continue
                    raw_tag = col.strip()
                    obs = self._build_observation(
                        raw_tag, raw_val.strip(), ts, None, ref_time, report
                    )
                    if obs:
                        observations.append(obs)
                        report.accepted_rows += 1
        else:
            # Long format
            for row in reader:
                report.total_rows += 1
                ts_str  = row.get(self.timestamp_col, "").strip()
                raw_tag = row.get(self.tag_col, "").strip()
                raw_val = row.get(self.value_col, "").strip()
                raw_q   = row.get(self.quality_col, "").strip() or None
                if not (ts_str and raw_tag and raw_val):
                    report.dropped_rows += 1
                    continue
                try:
                    ts = _parse_ts(ts_str)
                except ValueError:
                    report.dropped_rows += 1
                    continue
                obs = self._build_observation(
                    raw_tag, raw_val, ts, raw_q, ref_time, report
                )
                if obs:
                    observations.append(obs)
                    report.accepted_rows += 1
                else:
                    report.dropped_rows += 1

        return observations, report

    def _build_observation(
        self,
        raw_tag: str,
        raw_val: str,
        ts: datetime,
        raw_quality: Optional[str],
        ref_time: datetime,
        report: IngestionReport,
    ) -> Optional[TaggedObservation]:
        # Resolve tag
        canonical, found = self.normaliser.normalise(raw_tag)
        if not found:
            if canonical not in report.unresolved_tags:
                report.unresolved_tags.append(canonical)
            return None

        # Lookup component
        mapping = self.registry.lookup(canonical)
        if mapping is None:
            if canonical not in report.unmapped_sensors:
                report.unmapped_sensors.append(canonical)
            return None

        # Parse value
        try:
            value = float(raw_val)
        except ValueError:
            return None

        quality = self.time_policy.classify_quality(ts, ref_time, raw_quality)

        return TaggedObservation(
            site             = mapping.site,
            plant_area       = mapping.plant_area,
            unit_id          = mapping.unit_id,
            component_id     = mapping.component_id,
            component_type   = mapping.component_type,
            sensor_id        = canonical,
            timestamp        = ts,
            measurement_type = mapping.measurement_type,
            value            = value,
            unit             = mapping.unit,
            quality          = quality,
            stream_id        = mapping.stream_id,
        )


# ---------------------------------------------------------------------------
# JSON tag-value stream adapter
# ---------------------------------------------------------------------------

class JSONStreamAdapter:
    """
    Reads a JSON array or newline-delimited JSON of tag-value records.
    Each record must have at minimum: timestamp, tag/sensor_id, value.

    Example record:
    {
      "timestamp": "2026-04-06T10:15:00Z",
      "sensor_id": "PT-8812",
      "value": 184.2,
      "quality": "good"
    }
    """

    def __init__(
        self,
        normaliser: TagNormaliser,
        registry: ComponentRegistry,
        time_policy: Optional[TimeAlignmentPolicy] = None,
    ):
        self.normaliser  = normaliser
        self.registry    = registry
        self.time_policy = time_policy or TimeAlignmentPolicy()

    def ingest(
        self,
        json_text: str,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[List[TaggedObservation], IngestionReport]:
        ref_time = reference_time or datetime.now(timezone.utc)
        report = IngestionReport()

        # Accept both JSON array and NDJSON
        records: List[Dict[str, Any]] = []
        text = json_text.strip()
        if text.startswith("["):
            records = json.loads(text)
        else:
            for line in text.splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))

        report.total_rows = len(records)
        observations: List[TaggedObservation] = []

        for rec in records:
            raw_tag = rec.get("sensor_id") or rec.get("tag") or ""
            raw_val = rec.get("value")
            ts_str  = rec.get("timestamp") or rec.get("ts") or ""
            raw_q   = rec.get("quality") or rec.get("q")

            if not (raw_tag and raw_val is not None and ts_str):
                report.dropped_rows += 1
                continue

            try:
                ts    = _parse_ts(ts_str)
                value = float(raw_val)
            except (ValueError, TypeError):
                report.dropped_rows += 1
                continue

            canonical, found = self.normaliser.normalise(raw_tag)
            if not found:
                if canonical not in report.unresolved_tags:
                    report.unresolved_tags.append(canonical)
                report.dropped_rows += 1
                continue

            mapping = self.registry.lookup(canonical)
            if mapping is None:
                if canonical not in report.unmapped_sensors:
                    report.unmapped_sensors.append(canonical)
                report.dropped_rows += 1
                continue

            quality = self.time_policy.classify_quality(ts, ref_time, str(raw_q) if raw_q else None)

            observations.append(TaggedObservation(
                site             = mapping.site,
                plant_area       = mapping.plant_area,
                unit_id          = mapping.unit_id,
                component_id     = mapping.component_id,
                component_type   = mapping.component_type,
                sensor_id        = canonical,
                timestamp        = ts,
                measurement_type = mapping.measurement_type,
                value            = value,
                unit             = mapping.unit,
                quality          = quality,
                stream_id        = mapping.stream_id,
            ))
            report.accepted_rows += 1

        return observations, report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
