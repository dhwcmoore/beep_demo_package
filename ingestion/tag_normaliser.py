"""
ingestion/tag_normaliser.py — VeriStrain Scotford
Tag normalisation layer for raw plant historian inputs.

Industrial data arrives with inconsistent tag formats:
  "PT-8812" / "pt_8812" / "Pressure_8812" / "HC1_PT_8812"
All must resolve to the canonical sensor ID ("PT-8812") before
entering the analysis pipeline.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


class TagNormaliser:
    """
    Maps raw historian tag strings to canonical sensor IDs.
    Accepts an explicit tag_map (from site profile) plus applies
    heuristic normalisation as a fallback.
    """

    def __init__(self, tag_map: Dict[str, str]):
        """
        tag_map: keys are lower-case normalised variants,
                 values are canonical sensor IDs.
        """
        self._tag_map = tag_map
        self._miss_log: List[str] = []

    def normalise(self, raw_tag: str) -> Tuple[str, bool]:
        """
        Returns (canonical_id, was_found).
        If not found, returns (raw_tag, False) and logs the miss.
        """
        normalised = self._normalise_key(raw_tag)
        if normalised in self._tag_map:
            return self._tag_map[normalised], True

        # Try stripping common prefixes (unit codes, site codes)
        stripped = self._strip_prefix(normalised)
        if stripped and stripped in self._tag_map:
            return self._tag_map[stripped], True

        # Try heuristic reconstruction from type letter + number
        heuristic = self._heuristic_lookup(normalised)
        if heuristic:
            return heuristic, True

        self._miss_log.append(raw_tag)
        return raw_tag, False

    def normalise_batch(
        self, raw_tags: List[str]
    ) -> Dict[str, Tuple[str, bool]]:
        """Normalise a list of tags, returning {raw: (canonical, found)}."""
        return {tag: self.normalise(tag) for tag in raw_tags}

    @property
    def missed_tags(self) -> List[str]:
        """Tags that could not be resolved to a canonical ID."""
        return list(self._miss_log)

    def clear_miss_log(self) -> None:
        self._miss_log.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_key(raw: str) -> str:
        """Convert raw tag to a canonical lookup key (lower-case, hyphens to underscores)."""
        s = raw.strip().lower()
        s = re.sub(r"[-\s]+", "_", s)    # hyphens and spaces → underscores
        s = re.sub(r"[^a-z0-9_]", "", s) # remove any other non-alphanum
        return s

    @staticmethod
    def _strip_prefix(normalised: str) -> Optional[str]:
        """Remove known unit prefix codes (HC1_, HC2_, HT1_, etc.)."""
        pattern = re.compile(
            r"^(?:hc[0-9]+|ht[0-9]+|fp[0-9]+|fr[0-9]+|sc[0-9]+)_(.+)$"
        )
        m = pattern.match(normalised)
        return m.group(1) if m else None

    @staticmethod
    def _heuristic_lookup(normalised: str) -> Optional[str]:
        """
        Attempt to reconstruct a canonical tag like "PT-8812" from forms
        like "pt_8812" or "pressure_8812".
        """
        # Map common word forms to instrument type codes
        type_map = {
            "pt": "PT", "pressure": "PT", "press": "PT",
            "ft": "FT", "flow": "FT",
            "tt": "TT", "temperature": "TT", "temp": "TT",
            "lt": "LT", "level": "LT",
            "xv": "XV", "valve": "XV",
            "at": "AT", "analyzer": "AT",
            "it": "IT", "current": "IT",
            "st": "ST", "speed": "ST",
        }
        # Pattern: <type>_<number>
        m = re.match(r"^([a-z]+)_([0-9]+)$", normalised)
        if m:
            type_code = type_map.get(m.group(1))
            if type_code:
                return f"{type_code}-{m.group(2)}"
        return None
