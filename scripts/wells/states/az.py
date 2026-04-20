"""
Arizona — AOGCC wells via NM-hosted ArcGIS MapServer.

Source: Arizona Oil & Gas Conservation Commission (AOGCC) / AZ Dept of Environmental Quality
  Service: https://mercator.env.nm.gov/server/rest/services/azdeq/azogcc/MapServer/0
  Layers: 0=Oil Wells, 1=Gas Wells, 2=CO2 Wells, 3=Miscellaneous Wells
  Verified 2026-04 — ~1,196 wells across all layers (combined via layer 0 which serves full set)

~1,200 wells; small producing state (SE corner near NM border + scattered).
"""

import datetime
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

AZ_MAP_SERVER = "https://mercator.env.nm.gov/server/rest/services/azdeq/azogcc/MapServer/0"

_config = BaseConfig(
    state="AZ",
    source_label="az-aogcc",
    url=AZ_MAP_SERVER,
    bounds=(31.3, 37.0, -114.8, -109.0),
    output=Path("public/data/wells-az.json"),
    raw_dir=Path("data/raw/az"),
    require_depth=False,
    status_map={
        "ACTIVE":                   "Active",
        "ACTIVE PRODUCER":          "Active",
        "SHUT IN":                  "Inactive",
        "TEMPORARILY ABANDONED":    "Inactive",
        "ABANDONED TEMPORARY":      "Inactive",
        "TEMOPRARILY ABANDONED":    "Inactive",   # typo in source data
        "ABANDONED PLUGGED":        "Plugged & Abandoned",
        "ABANDONED PLUGGED AND ABANDONED": "Plugged & Abandoned",
        "ABANDONED JUNKED":         "Plugged & Abandoned",
        "PLANNED":                  "Permitted",
        "UNKNOWN":                  "Unknown",
    },
    well_type_map={
        "OIL":          "oil",
        "O":            "oil",
        "GAS":          "gas",
        "G":            "gas",
        "CO2":          "other",
        "O&GEXPLOR":    "oil-gas",
        "O&G":          "oil-gas",
        "GASSTORAGE":   "other",
        "GEOTHERMAL":   "other",
        "MISCELLANEOUS": "other",
    },
    field_map={
        # geometry x/y supplies lon/lat automatically via ArcGISAdapter
        "depth_ft":  ["drillertotaldepth", "trueverticaldepth"],
        "api":       ["apino", "APINO", "API_NO"],
        "operator":  ["operator", "OPERATOR"],
        "status":    ["status", "STATUS"],
        "well_type": ["welltype", "WELLTYPE"],
        "county":    ["county", "COUNTY"],
        "spud_date": ["spuddate", "SPUDDATE"],
    },
)


def _ms_to_date(val) -> str:
    """Convert ArcGIS Unix-ms timestamp to YYYY-MM-DD string, or '' if invalid."""
    if val is None:
        return ""
    try:
        ms = int(val)
    except (TypeError, ValueError):
        return str(val)
    if ms == 0:
        return ""
    try:
        dt = datetime.datetime.utcfromtimestamp(ms / 1000)
        return dt.strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return ""


class AZAdapter(ArcGISAdapter):
    """Arizona AOGCC wells — overrides normalize_row to handle ms timestamps."""

    def normalize_row(self, row: dict) -> Optional[dict]:
        # Convert spuddate ms timestamp to string before base processing
        for key in ("spuddate", "SPUDDATE"):
            if key in row and row[key] is not None:
                row[key] = _ms_to_date(row[key])
                break

        # Normalize status and well_type to uppercase for map lookup
        for key in ("status", "STATUS"):
            if key in row and row[key]:
                row[key] = str(row[key]).strip().upper()
                break
        for key in ("welltype", "WELLTYPE"):
            if key in row and row[key]:
                row[key] = str(row[key]).strip().upper()
                break

        return super().normalize_row(row)


adapter = AZAdapter(_config)
