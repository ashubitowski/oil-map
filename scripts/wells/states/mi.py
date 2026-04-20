"""
Michigan — EGLE Oil, Gas and Mineral Well Surface Locations (ArcGIS MapServer)

Source: Michigan EGLE GRMD Open Data ArcGIS MapServer
  https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/GrmdOpenData/MapServer/10
  ~92k wells. Geometry in WGS84.

Fields used:
  Y / X          — surface lat/lon (decimal degrees)
  DTD            — drilled total depth (ft)
  CompanyName    — operator
  PermitDate     — epoch ms timestamp (permit date, best available)
  WellStatus     — status string
  WellType       — well type string
  CountyName     — county name
  api_num        — API number
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/GrmdOpenData/MapServer/10"

_config = BaseConfig(
    state="MI",
    source_label="mi-egle",
    url=_URL,
    bounds=(41.7, 48.3, -90.5, -82.1),
    output=Path("public/data/wells-mi.json"),
    raw_dir=Path("data/raw/mi"),
    require_depth=False,
    status_map={
        "ACTIVE":                           "Active",
        "PRODUCING":                        "Active",
        "DRILLING COMPLETED":               "Active",
        "INJECTION SUSPENDED":              "Inactive",
        "SHUT_IN":                          "Inactive",
        "TEMPORARILY ABANDONED":            "Inactive",
        "PLUGGED BACK":                     "Inactive",
        "SUSPENDED OPERATIONS":             "Inactive",
        "PLUGGING":                         "Inactive",
        "PLUGGING APPROVED":                "Plugged & Abandoned",
        "PLUGGING APPROVED - PART 616":     "Plugged & Abandoned",
        "PLUGGING COMPLETED":               "Plugged & Abandoned",
        "PLUGGING COMPLETED- PART 616":     "Plugged & Abandoned",
        "WELL COMPLETED":                   "Active",
        "ORPHAN":                           "Inactive",
        "PERMITTED WELL":                   "Permitted",
        "TERMINATED PERMIT":                "Unknown",
        "NOT AVAILABLE":                    "Unknown",
        "SUMP":                             "Unknown",
        "WATER SUPPLY":                     "Unknown",
    },
    well_type_map={
        "OIL WELL":                                 "oil",
        "NATURAL GAS WELL":                         "gas",
        "GAS CONDENSATE WELL":                      "gas",
        "GAS STORAGE WELL":                         "other",
        "GAS STORAGE OBSERVATION WELL":             "other",
        "GAS INJECTION WELL":                       "other",
        "CO2 INJECTION WELL":                       "other",
        "BRINE DISPOSAL WELL":                      "other",
        "GAS PRODUCTION AND BRINE DISPOSAL WELL":   "gas",
        "WATER INJECTION WELL":                     "other",
        "OTHER INJECTION WELL":                     "other",
        "LIQUIFIED PETROLEUM GAS STORAGE WELL":     "other",
        "OBSERVATION WELL":                         "other",
        "OTHER WELL":                               "other",
        "DRY HOLE":                                 "other",
        "LOST HOLE":                                "other",
        "LOCATION":                                 "other",
        "PART 625 DISPOSAL WELL":                   "other",
        "PART 625 NATURAL BRINE WELL":              "other",
        "PART 625 SOLUTION MINING WELL":            "other",
        "PART 625 STORAGE WELL":                    "other",
        "PART 625 TEST WELL":                       "other",
        "NOT AVAILABLE":                            "other",
    },
)


def _parse_epoch_ms(val) -> str:
    """Convert an epoch-millisecond timestamp to YYYY-MM-DD string, or ''."""
    if val is None:
        return ""
    try:
        ts = int(val) / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


class MIAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Coordinates come from geometry via ArcGISAdapter.parse() → _lat/_lon
        try:
            lat = float(row.get("_lat") or row.get("Y") or 0)
            lon = float(row.get("_lon") or row.get("X") or 0)
        except (TypeError, ValueError):
            return None

        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("api_num") or "").strip()

        status_raw = str(row.get("WellStatus") or "").strip().upper()
        status = cfg.resolve_status(status_raw)

        type_raw = str(row.get("WellType") or "").strip().upper()
        well_type = cfg.resolve_well_type(type_raw)

        operator = str(row.get("CompanyName") or "Unknown").strip() or "Unknown"
        county = str(row.get("CountyName") or "Unknown").strip().title() or "Unknown"

        try:
            depth_ft = int(float(row.get("DTD") or 0))
        except (TypeError, ValueError):
            depth_ft = 0

        spud_date = _parse_epoch_ms(row.get("PermitDate"))

        well_id = f"mi-{normalize_api(api_raw)}" if api_raw else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "MI",
            "source": "mi-egle",
            "well_type": well_type,
        }


adapter = MIAdapter(_config)
