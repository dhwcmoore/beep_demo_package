"""
site_profiles/scotford.py — VeriStrain Scotford
Site-specific configuration for the Scotford Upgrader deployment.

Contains:
  - Area definitions and safety criticality
  - Essential redundancy declarations
  - Escalation policies per area
  - Required sensor lists per unit
  - Tag normalisation map
  - Expected operating modes per unit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from industrial_schema import OperatingMode, SafetyCriticality
from topology_model import PlantRegion


# ---------------------------------------------------------------------------
# Site identity
# ---------------------------------------------------------------------------

SITE_NAME              = "Scotford"
SITE_DESCRIPTION       = "Scotford Upgrader — Alberta, Canada"
PROFILE_VERSION        = "scotford_profile_0.3"
RULESET_VERSION        = "industrial_rules_0.5"
TOPOLOGY_MODEL_VERSION = "scotford_topo_0.3"


# ---------------------------------------------------------------------------
# Area definitions
# ---------------------------------------------------------------------------

@dataclass
class AreaDefinition:
    area_id:            str
    display_name:       str
    safety_criticality: SafetyCriticality
    process_type:       str           # "upgrader" | "utility" | "offsites"
    expected_modes:     List[OperatingMode]
    critical_unit_ids:  List[str]
    notes:              Optional[str] = None


SCOTFORD_AREAS: List[AreaDefinition] = [
    AreaDefinition(
        area_id            = "UPGRADER",
        display_name       = "Upgrader Process",
        safety_criticality = SafetyCriticality.SAFETY_CRITICAL,
        process_type       = "upgrader",
        expected_modes     = [
            OperatingMode.STEADY_STATE,
            OperatingMode.PARTIAL_LOAD,
            OperatingMode.STARTUP,
            OperatingMode.SHUTDOWN,
        ],
        critical_unit_ids  = ["Hydrocracker-01", "Hydrocracker-02", "Fractionator-01"],
        notes              = "Primary upgrading process — highest consequence area",
    ),
    AreaDefinition(
        area_id            = "HYDROTREATER",
        display_name       = "Hydrotreater",
        safety_criticality = SafetyCriticality.HIGH,
        process_type       = "upgrader",
        expected_modes     = [
            OperatingMode.STEADY_STATE,
            OperatingMode.PARTIAL_LOAD,
            OperatingMode.STARTUP,
            OperatingMode.SHUTDOWN,
            OperatingMode.RECYCLE_MODE,
        ],
        critical_unit_ids  = ["Hydrotreater-01", "Hydrotreater-02"],
    ),
    AreaDefinition(
        area_id            = "FEED_PREP",
        display_name       = "Feed Preparation",
        safety_criticality = SafetyCriticality.HIGH,
        process_type       = "upgrader",
        expected_modes     = [
            OperatingMode.STEADY_STATE,
            OperatingMode.STARTUP,
            OperatingMode.SHUTDOWN,
            OperatingMode.MAINTENANCE_BYPASS,
        ],
        critical_unit_ids  = ["FeedPrep-01"],
    ),
    AreaDefinition(
        area_id            = "UTILITY",
        display_name       = "Utilities",
        safety_criticality = SafetyCriticality.MODERATE,
        process_type       = "utility",
        expected_modes     = [OperatingMode.STEADY_STATE, OperatingMode.PARTIAL_LOAD],
        critical_unit_ids  = [],
        notes              = "Peripheral utility area — moderate consequence weighting",
    ),
    AreaDefinition(
        area_id            = "OFFSITES",
        display_name       = "Offsites and Storage",
        safety_criticality = SafetyCriticality.LOW,
        process_type       = "offsites",
        expected_modes     = [OperatingMode.STEADY_STATE],
        critical_unit_ids  = [],
    ),
]


def area_by_id(area_id: str) -> Optional[AreaDefinition]:
    for a in SCOTFORD_AREAS:
        if a.area_id == area_id:
            return a
    return None


def criticality_for_area(area_id: str) -> str:
    area = area_by_id(area_id)
    return area.safety_criticality.value if area else SafetyCriticality.MODERATE.value


# ---------------------------------------------------------------------------
# Required sensors per unit
# ---------------------------------------------------------------------------

# These are the tags that must be present for a result to be considered
# fully observable. Missing tags degrade observability status.
REQUIRED_SENSORS_BY_UNIT: Dict[str, List[str]] = {
    "Hydrocracker-01": [
        "PT-8801", "PT-8802", "PT-8812", "FT-8801", "FT-8802",
        "TT-8801", "TT-8802", "LT-8801", "XV-8801", "XV-8802",
    ],
    "Hydrocracker-02": [
        "PT-8901", "PT-8902", "FT-8901", "FT-8902",
        "TT-8901", "LT-8901", "XV-8901",
    ],
    "Fractionator-01": [
        "PT-9001", "PT-9002", "FT-9001", "TT-9001", "TT-9002",
        "LT-9001", "LT-9002",
    ],
    "Hydrotreater-01": [
        "PT-7001", "PT-7002", "FT-7001", "TT-7001", "XV-7001",
    ],
    "Hydrotreater-02": [
        "PT-7101", "PT-7102", "FT-7101", "TT-7101", "XV-7101",
    ],
    "FeedPrep-01": [
        "PT-6001", "FT-6001", "FT-6002", "LT-6001", "XV-6001",
    ],
}


def required_sensors_for_area(area_id: str) -> List[str]:
    """All required sensors for every unit in the given area."""
    area = area_by_id(area_id)
    if area is None:
        return []
    sensors: List[str] = []
    for unit_id in area.critical_unit_ids:
        sensors.extend(REQUIRED_SENSORS_BY_UNIT.get(unit_id, []))
    return sensors


# ---------------------------------------------------------------------------
# Redundancy declarations
# ---------------------------------------------------------------------------
# Pairs of component IDs that form essential redundancy loops.
# If either half of a pair is unavailable, redundancy is flagged as lost.

ESSENTIAL_REDUNDANCY_PAIRS: List[tuple[str, str]] = [
    ("P-204A", "P-204B"),   # Hydrocracker feed pumps
    ("P-205A", "P-205B"),   # Hydrocracker charge pumps
    ("K-301A", "K-301B"),   # Recycle gas compressors
    ("E-401A", "E-401B"),   # Feed/effluent heat exchangers
    ("XV-8801", "XV-8802"),  # Hydrocracker block valves
]


# ---------------------------------------------------------------------------
# Tag normalisation map
# ---------------------------------------------------------------------------
# Maps raw plant historian tag variants to canonical internal sensor IDs.
# Keys are lower-case normalised forms; values are canonical IDs.

def _build_tag_map() -> Dict[str, str]:
    """
    Generates a normalisation dictionary.
    Raw tags may arrive as any of:
      "PT-8812" / "pt_8812" / "Pressure_8812" / "HC1_PT_8812"
    All should resolve to "PT-8812".
    """
    canonical_tags = [
        "PT-8801", "PT-8802", "PT-8812",
        "FT-8801", "FT-8802",
        "TT-8801", "TT-8802",
        "LT-8801",
        "XV-8801", "XV-8802",
        "PT-8901", "PT-8902",
        "FT-8901", "FT-8902",
        "TT-8901", "LT-8901", "XV-8901",
        "PT-9001", "PT-9002",
        "FT-9001", "TT-9001", "TT-9002",
        "LT-9001", "LT-9002",
        "PT-7001", "PT-7002",
        "FT-7001", "TT-7001", "XV-7001",
        "PT-7101", "PT-7102",
        "FT-7101", "TT-7101", "XV-7101",
        "PT-6001", "FT-6001", "FT-6002",
        "LT-6001", "XV-6001",
    ]
    tag_map: Dict[str, str] = {}
    for tag in canonical_tags:
        # Direct match (uppercase)
        tag_map[tag.lower()] = tag
        # Underscore variant: PT_8812
        tag_map[tag.lower().replace("-", "_")] = tag
        # Type + number only: pressure_8812
        parts = tag.split("-")
        if len(parts) == 2:
            type_part, num_part = parts
            type_names = {
                "PT": ["pressure", "press", "pt"],
                "FT": ["flow", "ft"],
                "TT": ["temperature", "temp", "tt"],
                "LT": ["level", "lt"],
                "XV": ["valve", "xv"],
            }
            for alias in type_names.get(type_part, []):
                tag_map[f"{alias}_{num_part}".lower()] = tag
            # Unit-prefixed variant: HC1_PT_8812
            for prefix in ("HC1", "HC2", "HT1", "HT2", "FP1", "FR1"):
                tag_map[f"{prefix.lower()}_{tag.lower().replace('-', '_')}"] = tag
    return tag_map


TAG_NORMALISATION_MAP: Dict[str, str] = _build_tag_map()


# ---------------------------------------------------------------------------
# Nominal loop structures
# ---------------------------------------------------------------------------
# Describes the expected closed-loop flow paths for each major unit.
# Used to construct the baseline physical topology.

@dataclass
class NominalLoopDeclaration:
    loop_id:      str
    unit_id:      str
    components:   List[str]   # ordered component IDs forming the loop
    loop_type:    str         # "feed" | "recycle" | "discharge" | "relief"
    stream_ids:   List[str]   # stream IDs on this loop


NOMINAL_LOOPS: List[NominalLoopDeclaration] = [
    NominalLoopDeclaration(
        loop_id    = "HC01-FeedLoop",
        unit_id    = "Hydrocracker-01",
        components = ["FeedLine-17", "P-204A", "E-401A", "R-101", "E-401B", "FeedLine-17"],
        loop_type  = "feed",
        stream_ids = ["FeedLine-17"],
    ),
    NominalLoopDeclaration(
        loop_id    = "HC01-RecycleLoop",
        unit_id    = "Hydrocracker-01",
        components = ["R-101", "K-301A", "H2-MakeupLine", "R-101"],
        loop_type  = "recycle",
        stream_ids = ["H2-MakeupLine"],
    ),
    NominalLoopDeclaration(
        loop_id    = "HC01-ReliefPath",
        unit_id    = "Hydrocracker-01",
        components = ["R-101", "PSV-8801", "Flare-Header"],
        loop_type  = "relief",
        stream_ids = ["ReliefLine-01"],
    ),
]


# ---------------------------------------------------------------------------
# Escalation policy overrides per area
# ---------------------------------------------------------------------------

@dataclass
class AreaEscalationPolicy:
    """
    Defines how the fusion engine should weight results for a given area.
    Used by scotford_pipeline to configure FusionConfig criticality multipliers.
    """
    area_id:                    str
    criticality_multiplier:     float
    require_dual_confirmation:  bool    # require both structural and signal evidence
    auto_escalate_threshold:    float   # composite score above which always escalate
    suppression_modes:          List[OperatingMode]  # modes where rules are suppressed


AREA_ESCALATION_POLICIES: List[AreaEscalationPolicy] = [
    AreaEscalationPolicy(
        area_id                   = "UPGRADER",
        criticality_multiplier    = 1.7,
        require_dual_confirmation = False,
        auto_escalate_threshold   = 5.0,
        suppression_modes         = [OperatingMode.MAINTENANCE_BYPASS, OperatingMode.SHUTDOWN],
    ),
    AreaEscalationPolicy(
        area_id                   = "HYDROTREATER",
        criticality_multiplier    = 1.3,
        require_dual_confirmation = False,
        auto_escalate_threshold   = 6.0,
        suppression_modes         = [OperatingMode.SHUTDOWN],
    ),
    AreaEscalationPolicy(
        area_id                   = "FEED_PREP",
        criticality_multiplier    = 1.3,
        require_dual_confirmation = True,
        auto_escalate_threshold   = 6.5,
        suppression_modes         = [OperatingMode.MAINTENANCE_BYPASS, OperatingMode.SHUTDOWN],
    ),
    AreaEscalationPolicy(
        area_id                   = "UTILITY",
        criticality_multiplier    = 1.0,
        require_dual_confirmation = True,
        auto_escalate_threshold   = 7.5,
        suppression_modes         = [OperatingMode.MAINTENANCE_BYPASS],
    ),
    AreaEscalationPolicy(
        area_id                   = "OFFSITES",
        criticality_multiplier    = 0.8,
        require_dual_confirmation = True,
        auto_escalate_threshold   = 8.0,
        suppression_modes         = [OperatingMode.MAINTENANCE_BYPASS, OperatingMode.SHUTDOWN],
    ),
]


def policy_for_area(area_id: str) -> Optional[AreaEscalationPolicy]:
    for p in AREA_ESCALATION_POLICIES:
        if p.area_id == area_id:
            return p
    return None


# ---------------------------------------------------------------------------
# Pre-built PlantRegion objects for Scotford topology
# ---------------------------------------------------------------------------

def build_scotford_regions() -> List[PlantRegion]:
    return [
        PlantRegion(
            region_id           = "HC01-FeedLoop",
            region_type         = "unit",
            member_components   = {"FeedLine-17", "P-204A", "P-204B", "E-401A", "E-401B", "R-101"},
            boundary_components = {"FeedLine-17", "R-101"},
            required_sensors    = ["PT-8812", "FT-8801", "FT-8802", "TT-8801"],
            safety_criticality  = SafetyCriticality.SAFETY_CRITICAL.value,
        ),
        PlantRegion(
            region_id           = "HC01-RecycleLoop",
            region_type         = "unit",
            member_components   = {"R-101", "K-301A", "K-301B", "H2-MakeupLine"},
            boundary_components = {"R-101", "H2-MakeupLine"},
            required_sensors    = ["PT-8801", "PT-8802", "FT-8801"],
            safety_criticality  = SafetyCriticality.HIGH.value,
        ),
        PlantRegion(
            region_id           = "HC01-Containment",
            region_type         = "containment",
            member_components   = {"R-101", "PSV-8801", "Flare-Header"},
            boundary_components = {"PSV-8801"},
            required_sensors    = ["PT-8812"],
            safety_criticality  = SafetyCriticality.SAFETY_CRITICAL.value,
            notes               = "Hydrocracker reactor containment boundary",
        ),
        PlantRegion(
            region_id           = "HC01-HighPressure",
            region_type         = "high_pressure",
            member_components   = {"R-101", "E-401A", "E-401B", "P-204A", "P-204B"},
            boundary_components = {"P-204A", "P-204B"},
            required_sensors    = ["PT-8801", "PT-8802", "PT-8812"],
            safety_criticality  = SafetyCriticality.SAFETY_CRITICAL.value,
        ),
        PlantRegion(
            region_id           = "HT01-FeedLoop",
            region_type         = "unit",
            member_components   = {"HT-Feed-01", "Hydrotreater-01", "HT-Effluent-01"},
            boundary_components = {"HT-Feed-01", "HT-Effluent-01"},
            required_sensors    = ["PT-7001", "PT-7002", "FT-7001", "TT-7001"],
            safety_criticality  = SafetyCriticality.HIGH.value,
        ),
    ]


# ---------------------------------------------------------------------------
# Profile summary (for audit output)
# ---------------------------------------------------------------------------

def scotford_profile_dict() -> Dict[str, Any]:
    return {
        "site":                  SITE_NAME,
        "description":           SITE_DESCRIPTION,
        "profile_version":       PROFILE_VERSION,
        "ruleset_version":       RULESET_VERSION,
        "topology_model_version": TOPOLOGY_MODEL_VERSION,
        "area_count":            len(SCOTFORD_AREAS),
        "areas":                 [a.area_id for a in SCOTFORD_AREAS],
        "essential_redundancy_pair_count": len(ESSENTIAL_REDUNDANCY_PAIRS),
        "nominal_loop_count":    len(NOMINAL_LOOPS),
    }
