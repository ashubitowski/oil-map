"""
Tennessee — TDEC Division of Oil and Gas Well Permits (ArcGIS FeatureServer)

Source: Tennessee Nature Conservancy / TDEC Oil and Gas Well Permits layer
  https://services.arcgis.com/F7DSX1DSNSiWmOqh/arcgis/rest/services/Tennessee_Oil_and_Gas_Well_Permits/FeatureServer/0
  ~16.5k wells. Permit-level data; no operational status field available.

Fields used:
  Latitude / Longitude       — surface coords (WGS84 decimal degrees)
  Permit_Date                — permit date string "DD-MON-YYYY" (used as spud_date proxy)
  Operator_Name              — operator
  Purpose_af_Well            — well purpose (Oil, Gas, Oil And Gas, NCG - Domestic Use)
  County                     — county name
  API_No                     — API number
  Permit_No                  — permit number (fallback id)

Notes:
  - No well status field exists; all records are "Permitted" by source definition.
  - No total depth field; depth_ft will be 0 for all records.
  - Permit_Date is stored as string "DD-MON-YYYY" (e.g., "11-JUL-2023").
"""

from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds, parse_spud_date

_URL = (
    "https://services.arcgis.com/F7DSX1DSNSiWmOqh/arcgis/rest/services"
    "/Tennessee_Oil_and_Gas_Well_Permits/FeatureServer/0"
)

_WELL_TYPE_MAP: dict[str, str] = {
    "Oil":               "oil",
    "Gas":               "gas",
    "Oil And Gas":       "oil-gas",
    "NCG - Domestic Use": "gas",
}

_config = BaseConfig(
    state="TN",
    source_label="tn-deg",
    url=_URL,
    bounds=(34.9, 36.7, -90.3, -81.6),
    output=Path("public/data/wells-tn.json"),
    raw_dir=Path("data/raw/tn"),
    require_depth=False,
    status_map={},        # no status field in source; handled in normalize_row
    well_type_map=_WELL_TYPE_MAP,
    field_map={
        "lat":       ["Latitude", "_lat"],
        "lon":       ["Longitude", "_lon"],
        "operator":  ["Operator_Name"],
        "status":    [],
        "well_type": ["Purpose_af_Well"],
        "county":    ["County"],
        "api":       ["API_No"],
    },
)


class TNAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("Latitude") or row.get("_lat") or 0)
            lon = float(row.get("Longitude") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_No") or "").strip()
        permit_no = row.get("Permit_No")

        # Derive well_id: prefer API, fall back to permit number
        if api_raw:
            well_id = f"tn-{normalize_api(api_raw)}"
        elif permit_no:
            well_id = f"tn-permit-{permit_no}"
        else:
            well_id = None

        # Parse permit date as spud_date proxy (format: "DD-MON-YYYY")
        permit_date_raw = str(row.get("Permit_Date") or "").strip()
        spud_date = parse_spud_date(permit_date_raw) if permit_date_raw else ""

        # No depth field available
        depth_ft = 0

        # No status field — all records are permitted wells
        status = "Permitted"

        # Map well type from Purpose_af_Well
        purpose_raw = str(row.get("Purpose_af_Well") or "").strip()
        well_type = _WELL_TYPE_MAP.get(purpose_raw, "other")

        operator = str(row.get("Operator_Name") or "Unknown").strip() or "Unknown"
        county = str(row.get("County") or "Unknown").strip() or "Unknown"

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "TN",
            "source": "tn-deg",
            "well_type": well_type,
        }


adapter = TNAdapter(_config)
