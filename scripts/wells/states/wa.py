"""
Washington — DNR Oil and Gas Wells (ArcGIS MapServer)

Source: Washington Geological Survey / DNR
  https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/Oil_and_Gas_Wells/MapServer/1
  ~1,000 wells. Point locations from 1890 to present.

Fields of interest:
  API_NUMBER, COMPANY_NAME, DEPTH_FEET, DRILL_START_DATE,
  WELL_STATUS, HYDROCARBON_SHOW, COUNTY, LATITUDE, LONGITUDE
"""

from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, parse_spud_date, is_in_bounds

_SERVICE_URL = (
    "https://gis.dnr.wa.gov/site1/rest/services"
    "/Public_Geology/Oil_and_Gas_Wells/MapServer/1"
)

_config = BaseConfig(
    state="WA",
    source_label="wa-dnr",
    url=_SERVICE_URL,
    bounds=(45.5, 49.0, -124.8, -116.9),
    output=Path("public/data/wells-wa.json"),
    raw_dir=Path("data/raw/wa"),
    require_depth=False,
    status_map={
        "COMPLETED": "Active",
        "DRILLED": "Active",
        "PLUGGED AND ABANDONED": "Plugged & Abandoned",
        "COMPLETED, PLUGGED, AND ABANDONED": "Plugged & Abandoned",
        "CONVERTED TO WATER WELL": "Inactive",
    },
    well_type_map={},  # WA uses HYDROCARBON_SHOW instead; mapped below
    field_map={
        "lat": ["LATITUDE"],
        "lon": ["LONGITUDE"],
        "depth_ft": ["DEPTH_FEET"],
        "api": ["API_NUMBER"],
        "operator": ["COMPANY_NAME"],
        "status": ["WELL_STATUS"],
        "well_type": ["HYDROCARBON_SHOW"],
        "county": ["COUNTY"],
        "spud_date": ["DRILL_START_DATE"],
    },
)

_HYDROCARBON_TYPE_MAP = {
    "OIL": "oil",
    "GAS": "gas",
    "GAS, OIL": "oil-gas",
    "OIL, GAS": "oil-gas",
}


class WAAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # LATITUDE/LONGITUDE are attribute fields on this layer
        try:
            lat = float(row.get("LATITUDE") or row.get("_lat") or 0)
            lon = float(row.get("LONGITUDE") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_NUMBER") or "").strip()
        operator = str(row.get("COMPANY_NAME") or "Unknown").strip() or "Unknown"
        county = str(row.get("COUNTY") or "Unknown").strip().title() or "Unknown"

        status_raw = str(row.get("WELL_STATUS") or "").strip().upper()
        status = cfg.status_map.get(status_raw, "Unknown")

        hydro_raw = str(row.get("HYDROCARBON_SHOW") or "").strip().upper()
        well_type = _HYDROCARBON_TYPE_MAP.get(hydro_raw, "other")

        # DRILL_START_DATE is a Unix timestamp in ms
        date_ms = row.get("DRILL_START_DATE")
        if isinstance(date_ms, (int, float)) and date_ms:
            from datetime import datetime, timezone
            try:
                dt = datetime.fromtimestamp(date_ms / 1000, tz=timezone.utc)
                spud_date = dt.date().isoformat()
            except (OSError, OverflowError, ValueError):
                spud_date = ""
        else:
            spud_date = parse_spud_date(str(date_ms or ""))

        depth_raw = row.get("DEPTH_FEET")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0

        return {
            "id": f"wa-{normalize_api(api_raw)}" if api_raw else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "WA",
            "source": "wa-dnr",
            "well_type": well_type,
        }


adapter = WAAdapter(_config)
