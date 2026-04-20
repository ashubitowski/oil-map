"""
Nevada — NDOM Oil Well Locations (ArcGIS REST FeatureServer)

Source: Nevada Division of Minerals (NDOM)
  https://services.arcgis.com/CXYUMoYknZtf5Qr3/arcgis/rest/services/OGHistoricData/FeatureServer/1
  ~743 wells.  Fields: Permit, Well, Status, API, Well_Type, Completion_Date, Field, Land_Status.
  Geometry is returned as WGS84 when outSR=4326 is requested.

No depth field is available in this source; require_depth=False.
"""

from pathlib import Path

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, parse_spud_date, is_in_bounds

_SERVICE_URL = (
    "https://services.arcgis.com/CXYUMoYknZtf5Qr3/arcgis/rest/services"
    "/OGHistoricData/FeatureServer/1"
)

_config = BaseConfig(
    state="NV",
    source_label="nv-minerals",
    url=_SERVICE_URL,
    bounds=(35.0, 42.0, -120.0, -114.0),
    output=Path("public/data/wells-nv.json"),
    raw_dir=Path("data/raw/nv"),
    require_depth=False,
    status_map={
        "IN USE":    "Active",
        "PENDING":   "Permitted",
        "SHUT-IN":   "Inactive",
        "PLUGGED":   "Plugged & Abandoned",
        "ABANDONED": "Plugged & Abandoned",
        "WITHDRAWN": "Unknown",
    },
    well_type_map={
        "PROD":  "oil",
        "INJ":   "injection",
        "STRAT": "other",
        "WW":    "other",
    },
)


class NVAdapter(ArcGISAdapter):
    """Nevada Division of Minerals well locations."""

    def normalize_row(self, row: dict) -> dict | None:
        cfg = self.config

        # Geometry comes back via _lat/_lon injected by ArcGISAdapter.parse()
        try:
            lat = float(row.get("_lat") or 0)
            lon = float(row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API") or "").strip()
        well_name = str(row.get("Well") or "").strip()

        status_raw = str(row.get("Status") or "").strip().upper()
        status = cfg.resolve_status(status_raw)

        well_type_raw = str(row.get("Well_Type") or "").strip().upper()
        well_type = cfg.resolve_well_type(well_type_raw)

        county = str(row.get("Field") or "Unknown").strip() or "Unknown"

        completion_raw = str(row.get("Completion_Date") or "").strip()
        spud_date = parse_spud_date(completion_raw)

        operator = str(row.get("Land_Status") or "Unknown").strip() or "Unknown"

        well_id = f"nv-{normalize_api(api_raw)}" if api_raw else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": 0,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "NV",
            "source": "nv-minerals",
            "well_type": well_type,
        }


adapter = NVAdapter(_config)
