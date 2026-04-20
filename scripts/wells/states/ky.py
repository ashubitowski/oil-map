"""
Kentucky — KGS (Kentucky Geological Survey) Oil/Gas Wells (ArcGIS MapServer)

Source: Kentucky Geological Survey ArcGIS MapServer
  https://kgs.uky.edu/arcgis/rest/services/KYOilGas/KYOilGasWells_SZ/MapServer/0
  ~123k wells. Updated regularly.

Fields used:
  north_latitude / west_longitude — surface coords (WGS84 decimal degrees)
  total_depth                     — depth (ft)
  operator / most_recent_operator — operator name
  date_spudded                    — epoch ms timestamp
  original_result                 — result/status code
  original_result_symbol          — symbol category (OIL, GAS, SRV, D&A, etc.)
  plugged                         — ESRI boolean: -1 = plugged, 0 = not plugged
  county_name                     — county
  API_Number                      — API number
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://kgs.uky.edu/arcgis/rest/services/KYOilGas/KYOilGasWells_SZ/MapServer/0"

# original_result codes observed in the dataset.
# plugged == -1 overrides to "Plugged & Abandoned" in normalize_row.
_STATUS_MAP: dict[str, str] = {
    # Active producers
    "OIL":  "Active",
    "GAS":  "Active",
    "O&G":  "Active",
    "DG":   "Active",    # development gas
    "CBM":  "Active",    # coal bed methane
    # Active service wells
    "WI":   "Active",    # water injection
    "GI":   "Active",    # gas injection
    "AI":   "Active",    # air injection
    "SRI":  "Active",    # salt water re-injection
    "ERI":  "Active",    # enhanced recovery injection
    "TRI":  "Active",    # tertiary recovery injection
    "TAI":  "Active",    # temporary abandoned injection
    "SWD":  "Active",    # salt water disposal
    "WD":   "Active",    # waste disposal
    "GS":   "Active",    # gas storage
    "SI":   "Active",    # service/injection
    "WS":   "Active",    # water supply
    "OB":   "Active",    # observation
    "CP":   "Active",    # core/pressure test
    "WW":   "Active",    # water well
    # Temporarily abandoned → Inactive
    "TA":   "Inactive",
    "IA":   "Inactive",  # inactive abandoned
    # Dry holes / Plugged & Abandoned
    "D&A":  "Plugged & Abandoned",
    "AB":   "Plugged & Abandoned",
    # Location / Permitted
    "LOC":  "Permitted",
    # Unknown
    "STR":  "Unknown",   # stratigraphic
}

# Derive well_type from original_result_symbol (cleaner grouping)
_WELL_TYPE_MAP: dict[str, str] = {
    "OIL":  "oil",
    "GAS":  "gas",
    "O&G":  "oil-gas",
    "CBM":  "gas",
    "D&A":  "other",    # dry hole
    "SRV":  "other",    # service well
    "MSC":  "other",    # miscellaneous
    "STR":  "other",    # stratigraphic
}

_config = BaseConfig(
    state="KY",
    source_label="ky-kgs",
    url=_URL,
    bounds=(36.5, 39.2, -89.6, -81.9),
    output=Path("public/data/wells-ky.json"),
    raw_dir=Path("data/raw/ky"),
    require_depth=False,
    status_map=_STATUS_MAP,
    well_type_map=_WELL_TYPE_MAP,
    field_map={
        "lat":       ["north_latitude", "_lat"],
        "lon":       ["west_longitude", "_lon"],
        "depth_ft":  ["total_depth"],
        "operator":  ["operator"],
        "status":    ["original_result"],
        "well_type": ["original_result_symbol"],
        "county":    ["county_name"],
        "api":       ["API_Number"],
    },
)


class KYAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("north_latitude") or row.get("_lat") or 0)
            lon = float(row.get("west_longitude") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        # west_longitude is stored as negative (west), but verify in bounds
        if lon > 0:
            lon = -lon
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_Number") or "").strip()

        depth_raw = row.get("total_depth")
        try:
            depth_ft = int(depth_raw) if depth_raw is not None else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # date_spudded is epoch milliseconds
        spud_ms = row.get("date_spudded")
        spud_date = ""
        if spud_ms:
            try:
                dt = datetime.fromtimestamp(int(spud_ms) / 1000, tz=timezone.utc)
                if dt.year >= 1850:
                    spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        result_code = str(row.get("original_result") or "").strip()
        symbol_code = str(row.get("original_result_symbol") or "").strip()
        plugged = row.get("plugged")

        # Plugged flag overrides status (-1 = True in ESRI SmallInteger boolean)
        if plugged == -1:
            status = "Plugged & Abandoned"
        else:
            status = cfg.resolve_status(result_code)

        well_type = cfg.resolve_well_type(symbol_code)

        # Prefer most_recent_operator if available; fall back to operator
        operator = (
            str(row.get("most_recent_operator") or "").strip()
            or str(row.get("operator") or "").strip()
            or "Unknown"
        )

        county = str(row.get("county_name") or "Unknown").strip() or "Unknown"

        well_id = f"ky-{normalize_api(api_raw)}" if api_raw else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "KY",
            "source": "ky-kgs",
            "well_type": well_type,
        }


adapter = KYAdapter(_config)
