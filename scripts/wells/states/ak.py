"""
Alaska — AOGCC Well Surface Hole Locations

Source: Alaska Oil and Gas Conservation Commission (AOGCC) via ArcGIS FeatureServer
  https://services1.arcgis.com/7HDiw78fcUiM2BWn/arcgis/rest/services/Well_Surface_Hole_Location/FeatureServer/0
  ~10k wells. Updated regularly (live AOGCC data).

Fields used:
  WellHeadLat / WellHeadLong  — surface coordinates (decimal degrees)
  DrillerTotalDepth            — depth (ft)
  Operator                     — operator name
  SpudDate                     — epoch ms timestamp
  CurrentStatus                — text status (e.g. "Oil well, single completion")
  CurrentClass                 — well class (Development, Exploratory, Service, etc.)
  GeographicArea               — borough/area (county equivalent)
  APINumber                    — API number
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://services1.arcgis.com/7HDiw78fcUiM2BWn/arcgis/rest/services/Well_Surface_Hole_Location/FeatureServer/0"

_config = BaseConfig(
    state="AK",
    source_label="ak-aogcc",
    url=_URL,
    bounds=(54.5, 71.5, -168.0, -130.0),
    output=Path("public/data/wells-ak.json"),
    raw_dir=Path("data/raw/ak"),
    require_depth=False,
    status_map={
        # Active producing wells
        "Oil well, single completion":                  "Active",
        "Oil well, dual completion":                    "Active",
        "Commingled well (dual), oil":                  "Active",
        "Commingled well (triple), oil":                "Active",
        "Gas well, single completion":                  "Active",
        "Gas well, dual completion":                    "Active",
        "Gas well, triple completion":                  "Active",
        "Gas well & Storage well; produce only":        "Active",
        "Gas well (dual) & Storage well; produce only": "Active",
        # Injection / disposal wells (active)
        "Water injection, single completion":           "Active",
        "Water injection, dual completion":             "Active",
        "Water injection, single pool, two tbg strings": "Active",
        "Water alt gas injection":                      "Active",
        "Gas injection, single completion":             "Active",
        "Gas storage well; inject & produce":           "Active",
        "Disposal injection well, Class 1":             "Active",
        "Disposal injection well, Class 2":             "Active",
        "Disposal injection well, Class 1 & 2":        "Active",
        # Inactive / shut-in
        "Shut In":                                      "Inactive",
        "Suspended well":                               "Inactive",
        "Observation well":                             "Inactive",
        "Information well":                             "Inactive",
        "Water supply well":                            "Inactive",
        "Geothermal":                                   "Inactive",
        # Plugged & Abandoned
        "Plugged & Abandoned":                          "Plugged & Abandoned",
        "Administratively abandoned":                   "Plugged & Abandoned",
        "Surface Plug":                                 "Plugged & Abandoned",
        # Permitted
        "Permit cancelled":                             "Unknown",
        "Permit expired":                               "Unknown",
    },
    well_type_map={
        # Derived from CurrentStatus text in normalize_row
        # (not used directly via resolve_well_type — see below)
    },
    field_map={
        "lat":       ["WellHeadLat", "_lat"],
        "lon":       ["WellHeadLong", "_lon"],
        "depth_ft":  ["DrillerTotalDepth"],
        "operator":  ["Operator"],
        "status":    ["CurrentStatus"],
        "county":    ["GeographicArea"],
        "api":       ["APINumber"],
    },
)


def _derive_well_type(status: str, well_class: str) -> str:
    """Derive well_type from CurrentStatus and CurrentClass text."""
    s = (status or "").lower()
    c = (well_class or "").lower()

    if "oil" in s:
        return "oil"
    if "gas injection" in s or "gas storage" in s or "alt gas" in s:
        return "injection"
    if "gas" in s:
        return "gas"
    if "water injection" in s or "disposal" in s:
        return "disposal"
    if "water alt" in s:
        return "injection"
    if "geothermal" in s:
        return "other"
    if "stratigraphic" in c:
        return "other"
    if "service" in c:
        return "other"
    return "other"


class AKAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("WellHeadLat") or row.get("_lat") or 0)
            lon = float(row.get("WellHeadLong") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("APINumber") or "").strip()

        depth_raw = row.get("DrillerTotalDepth")
        try:
            depth_ft = int(depth_raw) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # SpudDate comes back as epoch milliseconds
        spud_ms = row.get("SpudDate")
        spud_date = ""
        if spud_ms:
            try:
                dt = datetime.fromtimestamp(int(spud_ms) / 1000, tz=timezone.utc)
                spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        current_status = str(row.get("CurrentStatus") or "").strip()
        current_class = str(row.get("CurrentClass") or "").strip()
        status = cfg.resolve_status(current_status)
        well_type = _derive_well_type(current_status, current_class)
        operator = str(row.get("Operator") or "Unknown").strip() or "Unknown"
        county = str(row.get("GeographicArea") or "Unknown").strip() or "Unknown"

        return {
            "id": f"ak-{normalize_api(api_raw)}" if api_raw else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "AK",
            "source": "ak-aogcc",
            "well_type": well_type,
        }


adapter = AKAdapter(_config)
