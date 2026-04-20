"""
Alabama — Oil and Gas Board (AOGB) GIS MapServer

Source: Alabama OGB GIS MapServer
  https://gis.ogb.state.al.us/arcgis/rest/services/OGB/OGBOnlineMap/MapServer/0
  ~16k wells.

Fields used:
  Latitude / Longitude  — surface coords (in attributes, outSR=4326)
  MD                    — measured depth (ft)
  Operator              — operator name
  SpudDate              — epoch ms timestamp
  WellStatus            — status code (AC, PA, DA, TA, SI, PR, ...)
  WellType              — type code (OIL, GAS, CM, SWD, ...)
  CountyName            — county
  API                   — API number
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://gis.ogb.state.al.us/arcgis/rest/services/OGB/OGBOnlineMap/MapServer/0"

_config = BaseConfig(
    state="AL",
    source_label="al-ogb",
    url=_URL,
    bounds=(30.1, 35.1, -88.5, -84.9),
    output=Path("public/data/wells-al.json"),
    raw_dir=Path("data/raw/al"),
    require_depth=False,
    status_map={
        # Active / producing
        "AC": "Active",
        "PR": "Active",
        "SI": "Inactive",      # shut-in
        "TA": "Inactive",      # temporarily abandoned
        "CV": "Inactive",      # converted to another use
        "PB": "Inactive",      # plugged back (partial plug, still has utility)
        # Plugged & Abandoned
        "PA": "Plugged & Abandoned",
        "DA": "Plugged & Abandoned",   # dry and abandoned
        "AB": "Plugged & Abandoned",   # abandoned
        # Permitted
        "AP": "Permitted",
        # Unknown / regulatory
        "RC": "Unknown",   # regulatory change
        "RJ": "Unknown",   # released jurisdiction
        "PW": "Unknown",
        "UN": "Unknown",
    },
    well_type_map={
        "OIL": "oil",
        "GAS": "gas",
        "GC":  "gas",       # gas condensate
        "GI":  "injection",
        "WI":  "injection",
        "SWD": "disposal",
        "WS":  "other",     # water supply
        "WW":  "other",     # water well
        "CM":  "other",     # coalbed methane
        "SHG": "other",     # shale gas
        "GS":  "other",     # gas storage
        "UN":  "other",
    },
    field_map={
        "lat":       ["Latitude", "_lat"],
        "lon":       ["Longitude", "_lon"],
        "depth_ft":  ["DTD", "LTD", "TVD"],
        "operator":  ["Operator"],
        "status":    ["WellStatus"],
        "well_type": ["WellType"],
        "county":    ["CountyName"],
        "api":       ["API"],
        "spud_date": ["SpudDate"],
    },
)


class ALAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Coordinates — prefer explicit Latitude/Longitude attrs, fall back to geometry
        try:
            lat = float(row.get("Latitude") or row.get("_lat") or 0)
            lon = float(row.get("Longitude") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API") or "").strip()

        # Depth — prefer DTD (Driller's Total Depth), fall back to LTD / TVD
        depth_raw = row.get("DTD") or row.get("LTD") or row.get("TVD")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw else 0
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

        status = cfg.resolve_status(str(row.get("WellStatus") or "").strip().upper())
        well_type = cfg.resolve_well_type(str(row.get("WellType") or "").strip().upper())
        operator = str(row.get("Operator") or "Unknown").strip() or "Unknown"
        county = str(row.get("CountyName") or "Unknown").strip() or "Unknown"

        return {
            "id": f"al-{normalize_api(api_raw)}" if api_raw else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "AL",
            "source": "al-ogb",
            "well_type": well_type,
        }


adapter = ALAdapter(_config)
