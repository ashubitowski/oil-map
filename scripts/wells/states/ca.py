"""
California — CalGEM WellSTAR wells via CNRA Hub CSV download.

Source: CA Dept of Conservation, CalGEM Division
  Hub: https://data.cnra.ca.gov/dataset/wellstar-oil-and-gas-wells
  Direct CSV: https://gis-cnra.hub.arcgis.com/api/download/v1/items/ef53080fdf894761858dd1728610b9a0/csv?layers=0
  Verified 2026-04

NOTE: CalGEM's public WellSTAR export does NOT include total depth. Wells are
included with depth_ft=1 (sentinel) so they appear on the map. Color/depth
visualization is not meaningful for CA wells.

~245k wells; San Joaquin Valley, Los Angeles Basin, Sacramento Valley.
"""

from pathlib import Path
from typing import Optional
from scripts.wells.adapters.direct_download import DirectDownloadAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import col, parse_spud_date, normalize_api, is_in_bounds

CA_CSV_URL = "https://gis-cnra.hub.arcgis.com/api/download/v1/items/ef53080fdf894761858dd1728610b9a0/csv?layers=0"

# WellTypeLabel → canonical type (more descriptive than WellType code)
WELLTYPE_LABEL_MAP = {
    "OIL": "oil", "OIL (CYCLIC STEAM)": "oil",
    "DRY GAS": "gas", "GAS": "gas", "COALBED METHANE": "gas",
    "OIL & GAS": "oil-gas",
    "WATER INJECTION": "injection", "STEAMFLOOD INJECTION": "injection",
    "CYCLIC STEAM": "injection", "GAS INJECTION": "injection",
    "WATER DISPOSAL": "disposal",
    "GEOTHERMAL": "other", "DRY HOLE": "other", "OBSERVATION": "other",
}

_config = BaseConfig(
    state="CA",
    source_label="ca-calgem",
    url=CA_CSV_URL,
    raw_filename="wellstar_wells.csv",
    require_depth=False,
    bounds=(32.5, 42.1, -124.5, -114.1),
    output=Path("public/data/wells-ca.json"),
    raw_dir=Path("data/raw/ca"),
    status_map={
        "ACTIVE": "Active",
        "NEW": "Active",
        "IDLE": "Inactive",
        "CANCELED": "Inactive",
        "CANCELLED": "Inactive",
        "BURIED": "Inactive",
        "PLUGGED": "Plugged & Abandoned",
        "PLUGGEDONLY": "Plugged & Abandoned",
        "NOTCALGEMJURISDICTION": "Unknown",
    },
    well_type_map={},  # not used — CAAdapter uses WellTypeLabel
    field_map={
        "lat": ["Latitude", "LATITUDE"],
        "lon": ["Longitude", "LONGITUDE"],
        "depth_ft": [],  # no depth in this source
        "api": ["API"],
        "operator": ["OperatorName"],
        "status": ["WellStatus"],
        "well_type": ["WellTypeLabel", "WellType"],
        "county": ["CountyName"],
        "spud_date": ["SpudDate"],
    },
)


class CAAdapter(DirectDownloadAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        import math
        cfg = self.config

        lat_s = col(row, "Latitude", "LATITUDE")
        lon_s = col(row, "Longitude", "LONGITUDE")
        try:
            lat, lon = float(lat_s), float(lon_s)
        except (ValueError, TypeError):
            return None
        if not math.isfinite(lat) or not math.isfinite(lon):
            return None
        if lat == 0.0 and lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api = col(row, "API")
        operator = col(row, "OperatorName") or "Unknown"
        status = cfg.resolve_status(col(row, "WellStatus"))
        county = col(row, "CountyName") or "Unknown"
        spud = parse_spud_date(col(row, "SpudDate"))

        # Use WellTypeLabel (more descriptive) then fall back to WellType code
        type_label = col(row, "WellTypeLabel").upper()
        well_type = WELLTYPE_LABEL_MAP.get(type_label, "other")

        return {
            "id": f"ca-{normalize_api(api)}" if api else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": 1,  # no depth in CalGEM public export
            "operator": operator,
            "spud_date": spud,
            "status": status,
            "county": county,
            "state": "CA",
            "source": "ca-calgem",
            "well_type": well_type,
        }


adapter = CAAdapter(_config)
