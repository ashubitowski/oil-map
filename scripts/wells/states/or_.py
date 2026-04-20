"""
Oregon — DOGAMI Oil & Gas Wells via ArcGIS FeatureServer.

Source: Oregon Department of Geology and Mineral Industries (DOGAMI),
  Mineral Land Regulation & Reclamation (MLRR)
  Service: OG_wells_1_29_21_UPDATE2, Layer 0
  https://services.arcgis.com/jDGuO8tYggdCCnUJ/arcgis/rest/services/OG_wells_1_29_21_UPDATE2/FeatureServer/0
  Verified 2026-04

~669 wells (Oregon has limited oil/gas production; most activity in eastern OR).

Fields:
  PermitID   — API-style permit number (e.g. "36-001-00003")
  Permittee  — operator name
  WellType   — Producer, Exploration, Gas Injection/Withdrawal, Water Disposal, etc.
  Status     — Unknown, Closed, Cancelled, Denied, Withdrawn, Permitted, Admin
  County     — county name
  Depth      — total depth in feet (integer attribute)
  Latitude   — WGS84 lat (attribute column)
  Longitude  — WGS84 lon (attribute column)
  Applicatio — application date string (used as spud_date proxy)

require_depth=False because many historic wells lack depth records.
"""

from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import is_in_bounds, normalize_api, parse_spud_date

_OR_URL = (
    "https://services.arcgis.com/jDGuO8tYggdCCnUJ/arcgis/rest/services"
    "/OG_wells_1_29_21_UPDATE2/FeatureServer/0"
)

_config = BaseConfig(
    state="OR",
    source_label="or-dogami",
    url=_OR_URL,
    bounds=(41.9, 46.3, -124.6, -116.5),
    output=Path("public/data/wells-or.json"),
    raw_dir=Path("data/raw/or"),
    require_depth=False,
    status_map={
        "PERMITTED": "Active",
        "ADMIN":     "Active",
        "CLOSED":    "Plugged & Abandoned",
        "CANCELLED": "Plugged & Abandoned",
        "DENIED":    "Unknown",
        "WITHDRAWN": "Unknown",
        "UNKNOWN":   "Unknown",
    },
    well_type_map={
        "PRODUCER":                     "oil",
        "FORMER PRODUCER - PLUGGED":    "oil",
        "EXPLORATION":                  "other",
        "GAS INJECTION/WITHDRAWAL":     "injection",
        "GAS INJECTION/WITHDRAWL":      "injection",  # source typo variant
        "WATER DISPOSAL":               "disposal",
    },
    field_map={},  # handled in normalize_row
)


class ORAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Coordinates — prefer geometry-derived _lat/_lon, fall back to attribute cols
        try:
            lat = float(row.get("_lat") or row.get("Latitude") or 0)
            lon = float(row.get("_lon") or row.get("Longitude") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # Depth
        try:
            depth_ft = int(float(row.get("Depth") or 0))
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # Permit ID doubles as the API number for Oregon (state code 36)
        permit_id = str(row.get("PermitID") or "").strip()

        operator = str(row.get("Permittee") or "Unknown").strip() or "Unknown"

        status_raw = str(row.get("Status") or "").strip().upper()
        status = cfg.resolve_status(status_raw)

        well_type_raw = str(row.get("WellType") or "").strip().upper()
        well_type = cfg.resolve_well_type(well_type_raw) if well_type_raw else "other"

        county = str(row.get("County") or "Unknown").strip() or "Unknown"

        # "Applicatio" is a truncated field name for "ApplicationDate"
        spud_date = parse_spud_date(str(row.get("Applicatio") or "").strip())

        well_id = f"or-{normalize_api(permit_id)}" if permit_id else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "OR",
            "source": "or-dogami",
            "well_type": well_type,
        }


adapter = ORAdapter(_config)
