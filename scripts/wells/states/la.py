"""
Louisiana — LDNR SONRIS Office of Conservation Oil/Gas Wells

Source: Louisiana DNR SONRIS GIS ArcGIS REST MapServer
  https://sonris-gis.dnr.la.gov/arcgis/rest/services/DNRSvc/OC/MapServer/0
  ~247k wells. Updated regularly.

Fields used:
  SURFACE_LAT_DEC_DEG / SURFACE_LONG_DEC_DEG  — surface coords
  MEASURED_DEPTH                               — depth (ft)
  ORG_OPER_NAME                                — operator
  SPUD_DATE                                    — epoch ms timestamp
  WELL_STATUS_CODE                             — numeric status code
  PRODUCT_TYPE_CODE                            — product type
  PARISH_NAME                                  — county equivalent
  API_NUM                                      — API number
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://sonris-gis.dnr.la.gov/arcgis/rest/services/DNRSvc/OC/MapServer/0"

_config = BaseConfig(
    state="LA",
    source_label="la-sonris",
    url=_URL,
    bounds=(28.8, 33.1, -94.1, -88.8),
    output=Path("public/data/wells-la.json"),
    raw_dir=Path("data/raw/la"),
    require_depth=False,
    status_map={
        # Active producing / injection
        "09": "Active",
        "10": "Active",
        "11": "Active",
        "12": "Active",
        "13": "Active",
        "14": "Active",
        "15": "Active",
        "16": "Active",
        "17": "Active",
        "33": "Active",   # shut-in but future utility
        # Inactive / temporarily abandoned
        "18": "Inactive",
        "20": "Inactive",
        "22": "Inactive",
        # Plugged & Abandoned
        "29": "Plugged & Abandoned",
        "30": "Plugged & Abandoned",
        "35": "Plugged & Abandoned",
        # Permitted
        "01": "Permitted",
        "02": "Permitted",
        # Unknown / bad data
        "03": "Unknown",   # permit expired
        "23": "Unknown",   # orphan
        "24": "Unknown",
        "25": "Unknown",
        "26": "Unknown",
        "27": "Unknown",
        "28": "Unknown",
        "34": "Unknown",
        "ZZZZZ": "Unknown",
    },
    well_type_map={
        "00": "other",    # no product / unknown
        "10": "oil",
        "20": "gas",
        "30": "oil-gas",
        "40": "injection",
        "50": "disposal",
        "60": "other",    # water supply
        "70": "other",    # stratigraphic test
        "80": "other",    # geothermal
        "90": "other",    # miscellaneous
    },
    field_map={
        "lat":       ["SURFACE_LAT_DEC_DEG", "_lat"],
        "lon":       ["SURFACE_LONG_DEC_DEG", "_lon"],
        "depth_ft":  ["MEASURED_DEPTH"],
        "operator":  ["ORG_OPER_NAME"],
        "status":    ["WELL_STATUS_CODE"],
        "well_type": ["PRODUCT_TYPE_CODE"],
        "county":    ["PARISH_NAME"],
        "api":       ["API_NUM"],
    },
)


class LAAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("SURFACE_LAT_DEC_DEG") or row.get("_lat") or 0)
            lon = float(row.get("SURFACE_LONG_DEC_DEG") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_NUM") or "").strip()

        depth_raw = row.get("MEASURED_DEPTH")
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

        status = cfg.resolve_status(str(row.get("WELL_STATUS_CODE") or "").strip())
        well_type = cfg.resolve_well_type(str(row.get("PRODUCT_TYPE_CODE") or "").strip())
        operator = str(row.get("ORG_OPER_NAME") or "Unknown").strip() or "Unknown"
        county = str(row.get("PARISH_NAME") or "Unknown").strip() or "Unknown"

        return {
            "id": f"la-{normalize_api(api_raw)}" if api_raw else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "LA",
            "source": "la-sonris",
            "well_type": well_type,
        }


adapter = LAAdapter(_config)
