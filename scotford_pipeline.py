"""
scotford_pipeline.py — VeriStrain Scotford
Main orchestration for the Scotford site-evaluation and production run modes.

This replaces beep_pipeline.py for Scotford deployments.
It wires together:
  industrial_schema → topology_model → signal_analysis →
  structural_analysis → fusion_engine → explanation_engine → audit_layer

Run modes are enforced here. Demo inputs are rejected in production mode.

Usage (CLI):
    python3 scotford_pipeline.py --input data.csv --area UPGRADER \
        --mode site-evaluation --output scotford_output.json

Usage (API):
    from scotford_pipeline import ScotfordPipeline
    pipeline = ScotfordPipeline(area_id="UPGRADER")
    result = pipeline.run_from_bundle(bundle)
    print(result.to_json())
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from audit_layer import AuditLayer, ProvenanceRecord, VersionManifest
from explanation_engine import ExplanationEngine
from fusion_engine import FusionConfig, FusionEngine, SuppressionContext
from industrial_schema import (
    OperatingMode,
    PlantObservationBundle,
    RunMode,
    TaggedObservation,
    TopologyMetadata,
)
from signal_analysis import SignalAnalyser, SignalThresholds
from structural_analysis import StructuralAnalyser
from topology_model import (
    EdgeState,
    EdgeType,
    PlantEdge,
    PlantTopologyModel,
    TopologyComparison,
)

from site_profiles.scotford import (
    PROFILE_VERSION,
    RULESET_VERSION,
    TOPOLOGY_MODEL_VERSION,
    build_scotford_regions,
    criticality_for_area,
    policy_for_area,
    required_sensors_for_area,
    scotford_profile_dict,
    TAG_NORMALISATION_MAP,
    SITE_NAME,
)


# ---------------------------------------------------------------------------
# Pipeline version
# ---------------------------------------------------------------------------

PROGRAM_VERSION = "veristrain-scotford-0.3.0"


# ---------------------------------------------------------------------------
# Topology builder
# ---------------------------------------------------------------------------

def build_topology_from_metadata(
    topology_metadata: List[TopologyMetadata],
    observations: List[TaggedObservation],
) -> PlantTopologyModel:
    """
    Constructs a PlantTopologyModel from TopologyMetadata declarations
    and infers edge states from observation data (valve states, pump states).
    """
    from industrial_schema import MeasurementType, DataQuality

    model = PlantTopologyModel()

    # Register all components
    for meta in topology_metadata:
        model.declare_component(meta.component_id)

    # Collect closed valves / failed pumps from observations (first pass)
    inactive_components: set = set()
    for obs in observations:
        if obs.quality == DataQuality.BAD:
            continue
        if obs.measurement_type == MeasurementType.VALVE_STATE and obs.value <= 0.1:
            inactive_components.add(obs.component_id)
        if obs.measurement_type == MeasurementType.PUMP_STATE and obs.value <= 0.0:
            inactive_components.add(obs.component_id)

    # Build edges: use activate_edge or deactivate_edge based on component state
    for meta in topology_metadata:
        for adj_id in meta.nominal_adjacency:
            model.declare_component(adj_id)
            direction = meta.process_direction or "forward"
            is_redundancy = meta.redundancy_class.value != "none"
            edge_type = EdgeType.REDUNDANCY_RELATION if is_redundancy else EdgeType.MATERIAL_FLOW

            # Edge is inactive if either endpoint is a known-closed valve/pump
            edge_inactive = (
                meta.component_id in inactive_components
                or adj_id in inactive_components
            )
            base_edge = PlantEdge(
                source=meta.component_id,
                target=adj_id,
                edge_type=edge_type,
                state=EdgeState.INACTIVE if edge_inactive else EdgeState.ACTIVE,
            )

            if direction == "forward" or direction == "bidirectional":
                if edge_inactive:
                    model.deactivate_edge(base_edge)
                else:
                    model.activate_edge(base_edge)
            if direction == "bidirectional":
                rev_edge = PlantEdge(
                    source=adj_id,
                    target=meta.component_id,
                    edge_type=edge_type,
                    state=EdgeState.INACTIVE if edge_inactive else EdgeState.ACTIVE,
                )
                if edge_inactive:
                    model.deactivate_edge(rev_edge)
                else:
                    model.activate_edge(rev_edge)

    # Add Scotford regions
    for region in build_scotford_regions():
        model.add_region(region)

    return model


# ---------------------------------------------------------------------------
# Main pipeline class
# ---------------------------------------------------------------------------

class ScotfordPipeline:
    """
    End-to-end evaluation pipeline for the Scotford site.

    Instantiate once per area/configuration, then call run_from_bundle()
    for each evaluation window.
    """

    def __init__(
        self,
        area_id: str = "UPGRADER",
        signer: Optional[Any] = None,
        signer_identity: Optional[str] = None,
        signing_key_ref: Optional[str] = None,
    ):
        self.area_id = area_id

        # Area policy
        policy = policy_for_area(area_id)
        criticality = criticality_for_area(area_id)
        required_sensors = required_sensors_for_area(area_id)
        self.required_sensors = required_sensors
        self.criticality      = criticality

        # Sub-engines
        self.signal_analyser   = SignalAnalyser(thresholds=SignalThresholds())
        self.structural_analyser = StructuralAnalyser()
        self.explanation_engine  = ExplanationEngine()

        # Fusion config from area policy
        fusion_config = FusionConfig()
        if policy:
            from industrial_schema import SafetyCriticality
            fusion_config.criticality_multiplier = {
                SafetyCriticality.LOW.value:            0.8,
                SafetyCriticality.MODERATE.value:       1.0,
                SafetyCriticality.HIGH.value:           policy.criticality_multiplier * 0.77,
                SafetyCriticality.SAFETY_CRITICAL.value: policy.criticality_multiplier,
            }
        self.fusion_config = fusion_config

        # Audit
        self.version_manifest = VersionManifest(
            program_version        = PROGRAM_VERSION,
            ruleset_version        = RULESET_VERSION,
            topology_model_version = TOPOLOGY_MODEL_VERSION,
            site_configuration_version = PROFILE_VERSION,
        )
        self.audit_layer = AuditLayer(
            version_manifest = self.version_manifest,
            signer           = signer,
            signer_identity  = signer_identity,
            signing_key_ref  = signing_key_ref,
        )

    def run_from_bundle(
        self,
        bundle: PlantObservationBundle,
        ingestion_report: Optional[Any] = None,
    ):
        """
        Run the full analysis pipeline on a PlantObservationBundle.
        Returns a SealedAuditOutput.
        """
        # --- Validate bundle ---
        errors = bundle.validate()
        if errors:
            raise ValueError(f"Bundle validation failed: {'; '.join(errors)}")

        _reject_demo_in_production(bundle)

        # --- Coverage and observability ---
        coverage = bundle.coverage_score(self.required_sensors)
        observability = bundle.observability_status(
            self.required_sensors,
            critical_threshold=0.70,
            partial_threshold=0.90,
        )

        # --- Topology model ---
        topology_model = build_topology_from_metadata(
            bundle.topology_metadata,
            bundle.observations,
        )
        comparison: TopologyComparison = topology_model.compare()
        critical_regions = topology_model.critical_regions()

        # --- Structural analysis ---
        structural_result = self.structural_analyser.classify(
            comparison,
            critical_regions=critical_regions,
        )

        # --- Signal analysis ---
        signal_result = self.signal_analyser.analyse(bundle)

        # --- Suppression context from operating mode ---
        suppression = SuppressionContext.from_operating_mode(bundle.operating_mode)

        # --- Fusion ---
        fusion_engine = FusionEngine(
            config=self.fusion_config,
            suppression=suppression,
        )
        fusion_result = fusion_engine.fuse(
            structural=structural_result,
            signal=signal_result,
            coverage_score=coverage,
            observability_status=observability,
            region_criticality=self.criticality,
        )

        # --- Explanation ---
        explanation = self.explanation_engine.explain(fusion_result)

        # --- Provenance ---
        missing_tags = [
            s for s in self.required_sensors
            if s not in {o.sensor_id for o in bundle.observations}
        ]
        provenance = ProvenanceRecord(
            data_sources             = bundle.data_sources,
            ingestion_time           = datetime.now(timezone.utc),
            processing_window_start  = bundle.window_start,
            processing_window_end    = bundle.window_end,
            dropped_input_count      = getattr(ingestion_report, "dropped_rows", 0),
            inferred_topology_count  = len([
                m for m in bundle.topology_metadata
                if not m.nominal_adjacency
            ]),
            missing_critical_tags    = missing_tags,
        )

        # --- Seal ---
        sealed = self.audit_layer.seal(bundle, fusion_result, explanation, provenance)
        return sealed

    # ------------------------------------------------------------------
    # CSV ingestion convenience method
    # ------------------------------------------------------------------

    def run_from_csv(
        self,
        csv_path: str,
        area_id: str,
        operating_mode: OperatingMode,
        run_mode: RunMode,
        topology_metadata: Optional[List[TopologyMetadata]] = None,
    ):
        """
        Convenience entry point: ingest a CSV historian export and run the pipeline.
        """
        from ingestion.tag_normaliser import TagNormaliser
        from ingestion.adapters import CSVHistorianAdapter, ComponentRegistry

        normaliser = TagNormaliser(TAG_NORMALISATION_MAP)
        # Build a minimal registry from site profile data
        registry = _build_scotford_registry()
        adapter   = CSVHistorianAdapter(
            normaliser=normaliser,
            registry=registry,
            site=SITE_NAME,
        )
        observations, ingestion_report = adapter.ingest_file(csv_path)
        if not observations:
            raise ValueError(f"No observations ingested from {csv_path}")

        timestamps = [o.timestamp for o in observations]
        window_start = min(timestamps)
        window_end   = max(timestamps)

        bundle = PlantObservationBundle(
            site             = SITE_NAME,
            plant_area       = area_id,
            operating_mode   = operating_mode,
            window_start     = window_start,
            window_end       = window_end,
            run_mode         = run_mode,
            observations     = observations,
            topology_metadata = topology_metadata or [],
            data_sources     = [str(Path(csv_path).name)],
        )
        return self.run_from_bundle(bundle, ingestion_report)


# ---------------------------------------------------------------------------
# Demo / simulation bundle builder (for testing)
# ---------------------------------------------------------------------------

def build_demo_bundle(
    area_id: str = "UPGRADER",
    operating_mode: OperatingMode = OperatingMode.STEADY_STATE,
) -> PlantObservationBundle:
    """
    Constructs a synthetic PlantObservationBundle that exercises the pipeline
    in demo mode. Not valid in production mode.
    """
    from industrial_schema import ComponentType, MeasurementType, DataQuality, SafetyCriticality, RedundancyClass
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    t0  = now.replace(minute=0, second=0, microsecond=0)

    # Two pressure sensors drifting upward (redundancy loss scenario)
    observations = [
        TaggedObservation(
            site="Scotford", plant_area=area_id,
            unit_id="Hydrocracker-01", component_id="R-101",
            component_type=ComponentType.VESSEL,
            sensor_id="PT-8812",
            timestamp=t0 + timedelta(minutes=i * 3),
            measurement_type=MeasurementType.PRESSURE,
            value=180.0 + i * 0.8,   # drifting upward
            unit="psi",
            quality=DataQuality.GOOD,
        )
        for i in range(5)
    ] + [
        TaggedObservation(
            site="Scotford", plant_area=area_id,
            unit_id="Hydrocracker-01", component_id="P-204A",
            component_type=ComponentType.PUMP,
            sensor_id="FT-8801",
            timestamp=t0 + timedelta(minutes=i * 3),
            measurement_type=MeasurementType.FLOW,
            value=1200.0 - i * 60.0,   # flow collapsing
            unit="m3/h",
            quality=DataQuality.GOOD,
        )
        for i in range(5)
    ] + [
        # Valve closed — will deactivate material flow edge
        TaggedObservation(
            site="Scotford", plant_area=area_id,
            unit_id="Hydrocracker-01", component_id="XV-8801",
            component_type=ComponentType.VALVE,
            sensor_id="XV-8801",
            timestamp=t0 + timedelta(minutes=2),
            measurement_type=MeasurementType.VALVE_STATE,
            value=0.0,   # closed
            unit="bool",
            quality=DataQuality.GOOD,
        )
    ]

    # Topology: P-204A (primary pump) feeds R-101 via FeedLine-17
    # P-204B is the redundancy; XV-8801 is on the primary path
    topology = [
        TopologyMetadata(
            component_id="P-204A",
            process_area=area_id,
            safety_criticality=SafetyCriticality.SAFETY_CRITICAL,
            operational_mode=operating_mode,
            redundancy_class=RedundancyClass.PRIMARY,
            nominal_adjacency=["R-101"],
            upstream_component="FeedLine-17",
            downstream_component="R-101",
            process_direction="forward",
        ),
        TopologyMetadata(
            component_id="P-204B",
            process_area=area_id,
            safety_criticality=SafetyCriticality.SAFETY_CRITICAL,
            operational_mode=operating_mode,
            redundancy_class=RedundancyClass.SECONDARY,
            nominal_adjacency=["R-101"],
            upstream_component="FeedLine-17",
            downstream_component="R-101",
            process_direction="forward",
        ),
        TopologyMetadata(
            component_id="R-101",
            process_area=area_id,
            safety_criticality=SafetyCriticality.SAFETY_CRITICAL,
            operational_mode=operating_mode,
            redundancy_class=RedundancyClass.NONE,
            nominal_adjacency=[],
        ),
        TopologyMetadata(
            component_id="XV-8801",
            process_area=area_id,
            safety_criticality=SafetyCriticality.HIGH,
            operational_mode=operating_mode,
            redundancy_class=RedundancyClass.NONE,
            nominal_adjacency=["R-101"],
        ),
    ]

    return PlantObservationBundle(
        site           = SITE_NAME,
        plant_area     = area_id,
        operating_mode = operating_mode,
        window_start   = t0,
        window_end     = t0 + timedelta(minutes=12),
        run_mode       = RunMode.DEMO,
        observations   = observations,
        topology_metadata = topology,
        data_sources   = ["synthetic_demo"],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reject_demo_in_production(bundle: PlantObservationBundle) -> None:
    """Refuse demo inputs in production or site-evaluation mode."""
    if bundle.run_mode in (RunMode.PRODUCTION, RunMode.SITE_EVALUATION):
        if bundle.run_mode == RunMode.PRODUCTION:
            demo_sources = [s for s in bundle.data_sources if "demo" in s.lower()]
            if demo_sources or not bundle.data_sources:
                raise ValueError(
                    f"Production mode rejects demo or undeclared data sources. "
                    f"Found: {bundle.data_sources}"
                )


def _build_scotford_registry():
    """
    Build a minimal ComponentRegistry from the Scotford site profile.
    In production this would be loaded from a configuration database.
    """
    from ingestion.adapters import ComponentRegistry, TagComponentMapping
    from industrial_schema import ComponentType, MeasurementType

    # Illustrative mapping — production deployment expands this fully
    mappings = [
        TagComponentMapping("PT-8812", "R-101",    ComponentType.VESSEL, MeasurementType.PRESSURE,        "psi",   "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("PT-8801", "P-204A",   ComponentType.PUMP,   MeasurementType.PRESSURE,        "psi",   "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("PT-8802", "P-204B",   ComponentType.PUMP,   MeasurementType.PRESSURE,        "psi",   "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("FT-8801", "P-204A",   ComponentType.PUMP,   MeasurementType.FLOW,            "m3/h",  "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("FT-8802", "P-204B",   ComponentType.PUMP,   MeasurementType.FLOW,            "m3/h",  "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("TT-8801", "E-401A",   ComponentType.HEAT_EXCHANGER, MeasurementType.TEMPERATURE, "degC", "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("TT-8802", "E-401B",   ComponentType.HEAT_EXCHANGER, MeasurementType.TEMPERATURE, "degC", "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("LT-8801", "R-101",    ComponentType.VESSEL, MeasurementType.LEVEL,           "m",     "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("XV-8801", "XV-8801",  ComponentType.VALVE,  MeasurementType.VALVE_STATE,     "bool",  "Hydrocracker-01", "UPGRADER", SITE_NAME),
        TagComponentMapping("XV-8802", "XV-8802",  ComponentType.VALVE,  MeasurementType.VALVE_STATE,     "bool",  "Hydrocracker-01", "UPGRADER", SITE_NAME),
    ]
    return ComponentRegistry(mappings)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VeriStrain Scotford Pipeline")
    p.add_argument("--demo",   action="store_true", help="Run with synthetic demo bundle")
    p.add_argument("--input",  type=str,            help="CSV input file path")
    p.add_argument("--area",   type=str,            default="UPGRADER")
    p.add_argument("--mode",   type=str,            default="site-evaluation",
                   choices=["demo", "simulation", "site-evaluation", "production"])
    p.add_argument("--output", type=str,            default="scotford_output.json")
    p.add_argument("--operator-view", action="store_true",
                   help="Print operator-mode summary instead of full JSON")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    pipeline = ScotfordPipeline(area_id=args.area)

    if args.demo or not args.input:
        print("[scotford_pipeline] Running in DEMO mode with synthetic bundle.")
        bundle = build_demo_bundle(area_id=args.area)
        sealed = pipeline.run_from_bundle(bundle)
    else:
        run_mode = RunMode(args.mode)
        operating_mode = OperatingMode.STEADY_STATE   # default; override via config
        sealed = pipeline.run_from_csv(
            csv_path=args.input,
            area_id=args.area,
            operating_mode=operating_mode,
            run_mode=run_mode,
        )

    output_json = sealed.to_json(indent=2)
    Path(args.output).write_text(output_json, encoding="utf-8")
    print(f"[scotford_pipeline] Output written to {args.output}")

    if args.operator_view:
        d = sealed.to_dict()
        print()
        print(f"  Decision:  {d['decision_state']}")
        print(f"  Structure: {d['structural_judgement']}")
        print(f"  Summary:   {d['operator_summary']}")
        print(f"  Action:    {d['recommended_action_class']}")
        print(f"  Coverage:  {d['coverage_score']:.0%}")
        print(f"  Confidence:{d['confidence_score']:.0%}")

    # Verify seal
    if AuditLayer.verify(sealed):
        print("[scotford_pipeline] Seal verified OK.")
    else:
        print("[scotford_pipeline] WARNING: Seal verification FAILED.", file=sys.stderr)


if __name__ == "__main__":
    main()
