"""
Nebraska — Nebraska Oil and Gas Conservation Commission (NOGCC)

Source: NOGCC wells via ArcGIS Online FeatureServer
  https://services9.arcgis.com/OjHfU34Et3kVRT5y/arcgis/rest/services/Nebraska_Wells/FeatureServer/0
  ~22,575 wells.

Fields used:
  Lat / Long        — decimal degree coordinates stored as attributes
  Well_Statu        — two-letter status code
  Well_Type         — text well type
  Co_Name           — operator/company name
  County            — county name
  API_WellNo        — API number

No depth or spud_date fields available in this source.
"""

from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://services9.arcgis.com/OjHfU34Et3kVRT5y/arcgis/rest/services/Nebraska_Wells/FeatureServer/0"

_config = BaseConfig(
    state="NE",
    source_label="ne-nogcc",
    url=_URL,
    bounds=(39.9, 43.1, -104.1, -95.3),
    output=Path("public/data/wells-ne.json"),
    raw_dir=Path("data/raw/ne"),
    require_depth=False,
    status_map={
        # Active / producing
        "PR": "Active",     # Producing
        "AI": "Active",     # Active Injection
        "SI": "Active",     # Shut-In (temporarily not producing but viable)
        "WC": "Active",     # Well Completion (being completed)
        "PW": "Active",     # Producing Well (variant)
        # Inactive / temporarily abandoned
        "TA": "Inactive",   # Temporarily Abandoned
        "WS": "Inactive",   # Waiting on Status
        # Plugged & Abandoned
        "PA": "Plugged & Abandoned",   # Plugged and Abandoned
        "DA": "Plugged & Abandoned",   # Dry and Abandoned
        "JA": "Plugged & Abandoned",   # Junked and Abandoned
        "AB": "Plugged & Abandoned",   # Abandoned
        "AX": "Plugged & Abandoned",   # Abandoned (variant)
        "DM": "Plugged & Abandoned",   # Destroyed/Mechanically Abandoned
        "AL": "Plugged & Abandoned",   # Abandoned Location
        # Permitted / expired
        "PD": "Permitted",  # Permit Drilled (location staked)
        "EX": "Unknown",    # Expired Location
        "UN": "Unknown",    # Unknown
    },
    well_type_map={
        "OIL/GAS WELL":                          "oil",
        "DRY HOLE":                               "other",
        "NATURAL GAS WELL":                       "gas",
        "ENHANCED OIL RECOVERY - INJECTION":      "injection",
        "WATER INJECTION - DISPOSAL":             "disposal",
        "GAS INJECTION WELL":                     "injection",
        "GAS STORAGE":                            "other",
        "WATER SOURCE":                           "other",
        "GEOTHERMAL":                             "other",
        "STRATIGRAPHIC":                          "other",
        "JUNKED AND ABANDONED":                   "other",
        "STORAGE":                                "other",
        "EXPIRED LOCATION":                       "other",
        "UIC CLASS I":                            "disposal",
    },
    field_map={
        "lat":       ["Lat", "_lat"],
        "lon":       ["Long", "_lon"],
        "operator":  ["Co_Name"],
        "status":    ["Well_Statu"],
        "well_type": ["Well_Type"],
        "county":    ["County"],
        "api":       ["API_WellNo"],
    },
)


class NEAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Prefer attribute lat/lon; fall back to geometry (_lat/_lon)
        try:
            lat = float(row.get("Lat") or row.get("_lat") or 0)
            lon = float(row.get("Long") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_WellNo") or "").strip()
        operator = str(row.get("Co_Name") or "Unknown").strip() or "Unknown"
        county = str(row.get("County") or "Unknown").strip() or "Unknown"

        status_raw = str(row.get("Well_Statu") or "").strip().upper()
        status = cfg.resolve_status(status_raw)

        well_type_raw = str(row.get("Well_Type") or "").strip().upper()
        well_type = cfg.resolve_well_type(well_type_raw)

        return {
            "id": f"ne-{normalize_api(api_raw)}" if api_raw else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": 0,
            "operator": operator,
            "spud_date": "",
            "status": status,
            "county": county,
            "state": "NE",
            "source": "ne-nogcc",
            "well_type": well_type,
        }


adapter = NEAdapter(_config)
