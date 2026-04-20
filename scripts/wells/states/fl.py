"""
Florida — DEP Oil and Gas Wells

Source: Florida DEP ArcGIS REST MapServer (OpenData)
  https://ca.dep.state.fl.us/arcgis/rest/services/OpenData/OIL_WELLS/MapServer/0
  ~1,477 wells. Maintained by FL DEP Division of Water Resource Management.

Fields used:
  LATITUDE / LONGITUDE      — decimal degree coords (attribute, not geometry)
  TVD                       — true vertical depth (ft)
  COMPANY                   — operator/company name
  SPUD_DATE                 — epoch ms timestamp (drill date)
  CURRENT_STATUS            — well status string
  COUNTY                    — county name
  API_NO                    — API number
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://ca.dep.state.fl.us/arcgis/rest/services/OpenData/OIL_WELLS/MapServer/0"

# CURRENT_STATUS values observed:
#   PROD, PROD/TA, PROD/P&A -> production well, various end states
#   INJ, INJ/TA, INJ/P&A   -> injection well
#   SWD, SWD/P&A           -> salt water disposal
#   DRY HOLE/P&A           -> dry hole then plugged
#   P&A                    -> plugged and abandoned
#   TA                     -> temporarily abandoned
#   JUNKED                 -> junked (abandoned)
#   PENDING                -> permit pending
#   N/D                    -> not drilled

_STATUS_MAP = {
    "PROD":         "Active",
    "INJ":          "Active",
    "SWD":          "Active",
    "PROD/TA":      "Inactive",
    "INJ/TA":       "Inactive",
    "TA":           "Inactive",
    "PROD/P&A":     "Plugged & Abandoned",
    "INJ/P&A":      "Plugged & Abandoned",
    "SWD/P&A":      "Plugged & Abandoned",
    "DRY HOLE/P&A": "Plugged & Abandoned",
    "P&A":          "Plugged & Abandoned",
    "JUNKED":       "Plugged & Abandoned",
    "PENDING":      "Permitted",
    "N/D":          "Unknown",
}

_WELL_TYPE_MAP = {
    "PROD":         "oil",
    "PROD/TA":      "oil",
    "PROD/P&A":     "oil",
    "INJ":          "injection",
    "INJ/TA":       "injection",
    "INJ/P&A":      "injection",
    "SWD":          "disposal",
    "SWD/P&A":      "disposal",
    "DRY HOLE/P&A": "other",
    "P&A":          "other",
    "JUNKED":       "other",
    "PENDING":      "other",
    "N/D":          "other",
}

_config = BaseConfig(
    state="FL",
    source_label="fl-dep",
    url=_URL,
    bounds=(24.4, 31.1, -87.7, -79.9),
    output=Path("public/data/wells-fl.json"),
    raw_dir=Path("data/raw/fl"),
    require_depth=False,
    status_map=_STATUS_MAP,
    well_type_map=_WELL_TYPE_MAP,
    field_map={
        "lat":       ["LATITUDE", "_lat"],
        "lon":       ["LONGITUDE", "_lon"],
        "depth_ft":  ["TVD"],
        "operator":  ["COMPANY"],
        "status":    ["CURRENT_STATUS"],
        "well_type": ["CURRENT_STATUS"],
        "county":    ["COUNTY"],
        "api":       ["API_NO"],
    },
)


class FLAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Prefer attribute lat/lon; fall back to geometry (_lat/_lon)
        try:
            lat = float(row.get("LATITUDE") or row.get("_lat") or 0)
            lon = float(row.get("LONGITUDE") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_NO") or "").strip()

        depth_raw = row.get("TVD")
        try:
            depth_ft = int(depth_raw) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # SPUD_DATE comes back as epoch milliseconds
        spud_ms = row.get("SPUD_DATE")
        spud_date = ""
        if spud_ms:
            try:
                dt = datetime.fromtimestamp(int(spud_ms) / 1000, tz=timezone.utc)
                spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        raw_status = str(row.get("CURRENT_STATUS") or "").strip().upper()
        status = _STATUS_MAP.get(raw_status, "Unknown")
        well_type = _WELL_TYPE_MAP.get(raw_status, "other")

        operator = str(row.get("COMPANY") or "Unknown").strip() or "Unknown"
        county = str(row.get("COUNTY") or "Unknown").strip() or "Unknown"

        return {
            "id": f"fl-{normalize_api(api_raw)}" if api_raw else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "FL",
            "source": "fl-dep",
            "well_type": well_type,
        }


adapter = FLAdapter(_config)
