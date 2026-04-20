"""
South Carolina — SCDNR Coastal Plain Well Inventory
(ArcGIS FeatureServer, SCDNR Hydrology Section)

Source:
  https://services.arcgis.com/acgZYxoN5Oj8pDLa/arcgis/rest/services/
      SCDNR_Coastal_Plain_Well_Inventory/FeatureServer/0
  ~14,146 records: domestic, irrigation, public-supply, industrial, test,
  and observation wells maintained by the SC Department of Natural Resources
  Hydrology Section. Covers the Coastal Plain counties of South Carolina.

Background
----------
South Carolina has no active oil or natural gas production, and FracTracker
explicitly lists zero O&G wells in the state.  Historical petroleum exploration
was limited to the Dunbarton Triassic Basin (Aiken/Barnwell area) and a handful
of Coastal Plain test holes drilled in the 1950s–1980s.

The SCDNR Hydrology Section maintains the most comprehensive public well-point
database for the state.  While these are primarily water-supply wells, the
dataset includes geological TEST borings, SCGS-sampled wells, and deep
industrial/observational wells that document the subsurface stratigraphy.
This is the canonical source for SC subsurface point data.

Fields used:
  Lat_DD_NAD83 / Lon_DD_NAD83  — WGS84-compatible NAD83 decimal degrees
  DEPTH_D                       — drilled depth (feet)
  DRILL_YR / DRILL_MO           — drill year and month strings
  COUNTY                        — county name
  WELL_ID                       — SCDNR well identifier (e.g. AIK-1)
  OWNER                         — well owner (used as operator label)
  DRILLER                       — drilling company
  WELL_USE                      — use code (DOM, PS, IND, TEST, OBS, IRR, …)

WELL_USE → well_type mapping:
  TEST  → "other"   (geological test borings, SCGS monitoring)
  OBS   → "other"   (water-table observation wells)
  IND   → "other"   (industrial / deep process wells)
  PS    → "water"   (public water-supply)
  DOM   → "water"   (domestic water supply)
  IRR   → "water"   (irrigation)
  STB   → "other"   (standby)
  ABN   → "other"   (abandoned)
  DES   → "other"   (desilting / dewatering)
  FIRE  → "water"   (fire protection)
  REC   → "other"   (recreational/recharge)
  STK   → "water"   (stock water)
  UNU   → "other"   (unused)
  AC    → "other"   (air conditioning)

Notes:
  - No status field exists; all records are treated as "Unknown".
  - The OWNER field is used as the operator label.
  - Coordinates are stored as NAD83 decimal-degree attributes; the geometry
    is in a projected CRS (EPSG:26917) and is not used.
  - require_depth=False because many valid records lack depth data.
"""

from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import is_in_bounds, parse_spud_date

_URL = (
    "https://services.arcgis.com/acgZYxoN5Oj8pDLa/arcgis/rest/services"
    "/SCDNR_Coastal_Plain_Well_Inventory/FeatureServer/0"
)

# WELL_USE codes → canonical well_type
_WELL_TYPE_MAP: dict[str, str] = {
    "TEST": "other",   # geological test borings / SCGS monitoring wells
    "OBS":  "other",   # water-table observation wells
    "0BS":  "other",   # typo variant in source data
    "IND":  "other",   # industrial / deep process wells
    "ABN":  "other",   # abandoned
    "DES":  "other",   # desilting / dewatering
    "STB":  "other",   # standby
    "REC":  "other",   # recreational / recharge
    "UNU":  "other",   # unused
    "AC":   "other",   # air conditioning
    "GC":   "other",   # golf course
    "IN":   "other",   # infiltration
    "RS":   "other",   # remediation / recovery system
    "PS":   "water",   # public water-supply
    "DOM":  "water",   # domestic
    "IRR":  "water",   # irrigation
    "FIRE": "water",   # fire protection
    "STK":  "water",   # stock water
}

_config = BaseConfig(
    state="SC",
    source_label="sc-dnr",
    category="water-other",
    url=_URL,
    bounds=(32.0, 35.2, -83.4, -78.5),
    output=Path("public/data/wells-sc.json"),
    raw_dir=Path("data/raw/sc"),
    require_depth=False,
    status_map={},         # no status field; handled in normalize_row
    well_type_map=_WELL_TYPE_MAP,
    field_map={},          # all fields resolved manually in normalize_row
)


class SCAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Coordinates stored as NAD83 decimal-degree attributes
        try:
            lat = float(row.get("Lat_DD_NAD83") or 0)
            lon = float(row.get("Lon_DD_NAD83") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # Depth
        depth_raw = row.get("DEPTH_D")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw is not None else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # Drill date from DRILL_YR + DRILL_MO
        yr = str(row.get("DRILL_YR") or "").strip()
        mo = str(row.get("DRILL_MO") or "").strip().zfill(2)
        if yr and yr.isdigit() and len(yr) == 4:
            spud_date = f"{yr}-{mo}-01" if mo and mo != "00" else f"{yr}-01-01"
        else:
            spud_date = ""

        # Well type from WELL_USE
        use_code = str(row.get("WELL_USE") or "").strip().upper()
        well_type = _WELL_TYPE_MAP.get(use_code, "other")

        # Owner as operator label; fall back to driller, then Unknown
        owner = str(row.get("OWNER") or "").strip()
        driller = str(row.get("DRILLER") or "").strip()
        operator = owner or driller or "Unknown"

        # County
        county = str(row.get("COUNTY") or "Unknown").strip().title() or "Unknown"

        # ID from WELL_ID
        well_id_raw = str(row.get("WELL_ID") or "").strip()
        well_id = f"sc-{well_id_raw}" if well_id_raw else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": "Unknown",
            "county": county,
            "state": "SC",
            "source": "sc-dnr",
            "well_type": well_type,
        }


adapter = SCAdapter(_config)
