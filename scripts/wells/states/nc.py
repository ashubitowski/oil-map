"""
North Carolina — NC Geological Survey Core Library / Exploratory Wells
(via NC Department of Environmental Quality DEMLR)

Source: NC Geological Survey / NCDEQ DEMLR ArcGIS FeatureServer
  https://services2.arcgis.com/kCu40SDxsCGcuUWO/arcgis/rest/services/lccc_pts_2022_03_03/FeatureServer/0
  ~884 records: oil/gas exploration wells, coastal-plain test holes, hard-rock cores,
  and Triassic basin wells maintained by the NC Geological Survey Core Library.

Fields used:
  LAT_DD / LONG_DD   — surface coordinates in WGS84 decimal degrees
  HOLE_DEPTH         — total depth in feet
  DATE_DRILL         — drill date string (YYYY-MM-DD)
  COUNTY             — county name
  NCGS_ID            — NC Geological Survey identifier (used as well ID)
  WELL_NAME_         — well/borehole name (used as operator fallback label)
  TYPE2              — well/borehole category for well_type mapping

Notes:
  - NC has historically very limited oil/gas production (~129 exploration wells drilled,
    most activity in the 1980-90s in Lee and Chatham counties).
  - This dataset covers all NCGS core-library borings, not just oil/gas wells; the
    TYPE2 field is used to assign well_type.
  - No operator field exists; WELL_NAME_ is used as a descriptive label instead.
  - No well status field exists; all records are treated as "Unknown" status.
  - Coordinates are stored as LAT_DD / LONG_DD attributes in WGS84.
"""

from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import is_in_bounds, parse_spud_date

_URL = (
    "https://services2.arcgis.com/kCu40SDxsCGcuUWO/arcgis/rest/services"
    "/lccc_pts_2022_03_03/FeatureServer/0"
)

# Map TYPE2 values to canonical well_type strings
_WELL_TYPE_MAP: dict[str, str] = {
    "Oil / Natural Gas Exploration Wells": "oil-gas",
    "Triassic Basin Wells":                "oil-gas",   # hydrocarbon potential basins
    "Coastal Plain Wells":                 "other",
    "Hard Rock Cores":                     "other",
}

_config = BaseConfig(
    state="NC",
    source_label="nc-deq",
    url=_URL,
    bounds=(33.8, 36.6, -84.3, -75.5),
    output=Path("public/data/wells-nc.json"),
    raw_dir=Path("data/raw/nc"),
    require_depth=False,
    status_map={},        # no status field; handled in normalize_row
    well_type_map=_WELL_TYPE_MAP,
    field_map={},         # all fields resolved manually in normalize_row
)


class NCAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Coordinates stored as WGS84 decimal-degree attributes
        try:
            lat = float(row.get("LAT_DD") or 0)
            lon = float(row.get("LONG_DD") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # Depth
        depth_raw = row.get("HOLE_DEPTH")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # Drill date
        date_raw = str(row.get("DATE_DRILL") or "").strip()
        spud_date = parse_spud_date(date_raw) if date_raw else ""

        # Well type from TYPE2
        type2 = str(row.get("TYPE2") or "").strip()
        well_type = _WELL_TYPE_MAP.get(type2, "other")

        # No operator field — use well name as a descriptive label
        well_name = str(row.get("WELL_NAME_") or "Unknown").strip() or "Unknown"

        # County
        county = str(row.get("COUNTY") or "Unknown").strip().title() or "Unknown"

        # ID from NCGS_ID
        ncgs_id = str(row.get("NCGS_ID") or "").strip()
        well_id = f"nc-{ncgs_id}" if ncgs_id else None

        # No status field in source
        status = "Unknown"

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": well_name,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "NC",
            "source": "nc-deq",
            "well_type": well_type,
        }


adapter = NCAdapter(_config)
