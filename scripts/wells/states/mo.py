"""
Missouri — MODNR Oil & Gas Wells (ArcGIS MapServer)

Source: Missouri Department of Natural Resources, Missouri Geological Survey
  https://gis.dnr.mo.gov/host/rest/services/geology/oil_gas_wells/MapServer/0
  ~10,400 wells (non-confidential permitted wells).

Fields used:
  LATITUDE / LONGITUDE   — surface coords (WGS84 attributes)
  TOTAL_DPTH             — total depth (ft)
  OPERATOR               — operator name
  SPUD_DATE              — spud date (epoch ms)
  STATUS                 — well status
  WELL_TYPE              — well type description
  API_NUMBER             — API number (e.g. "037-20070")
  COUNTY                 — county name
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://gis.dnr.mo.gov/host/rest/services/geology/oil_gas_wells/MapServer/0"

_config = BaseConfig(
    state="MO",
    source_label="mo-dnr",
    url=_URL,
    bounds=(35.9, 40.6, -95.8, -89.1),
    output=Path("public/data/wells-mo.json"),
    raw_dir=Path("data/raw/mo"),
    require_depth=False,
    status_map={
        # Active (keys stored uppercase to match base.resolve_status() behaviour)
        "ACTIVE WELL":                                                          "Active",
        # Temporarily inactive
        "SHUT IN - EXTENDED":                                                   "Inactive",
        "SHUT IN - INCOMPLETE":                                                 "Inactive",
        "SHUT IN - COMPLETE":                                                   "Inactive",
        "INACTIVE \u2013 INITIAL 90 DAY WINDOW":                               "Inactive",
        "TEMPORARILY ABANDONED(IDLE)":                                          "Inactive",
        "PENDING SHUT IN APPROVAL":                                             "Inactive",
        "WATER WELL CONVERSION":                                                "Inactive",
        "ORPHANED":                                                             "Inactive",
        # Plugged / Abandoned
        "PLUGGED - APPROVED":                                                   "Plugged & Abandoned",
        "PLUGGED - NOT APPROVED":                                               "Plugged & Abandoned",
        "ABANDONED":                                                            "Plugged & Abandoned",
        "ABANDONED, KNOWN LOCATION AND VERIFIED":                               "Plugged & Abandoned",
        "ABANDONED, UNKNOWN LOCATION":                                          "Plugged & Abandoned",
        "ABANDONED, NO EVIDENCE OF EXISTENCE/ UNABLE TO FIND":                 "Plugged & Abandoned",
    },
    well_type_map={
        # Oil (keys stored uppercase to match base.resolve_well_type() behaviour)
        "OIL":                                                                  "oil",
        "HORIZONTAL OIL WELL":                                                  "oil",
        # Gas
        "GAS(CONVERTIONAL, COMMERCIAL)":                                        "gas",
        "GAS(PRIVATE USE)":                                                     "gas",
        "GAS(COALBED METHANE)":                                                 "gas",
        "GAS STORAGE WELLS":                                                    "gas",
        # Injection / disposal
        "INJECTION(CLASS II EOR)":                                              "injection",
        "INJECTION(CLASS II DISPOSAL)":                                         "disposal",
        "INJECTION(WATER CURTAIN)":                                             "injection",
        # Other
        "WATER WELL":                                                           "other",
        "WATER WELL, NON OIL/GAS RELATED (HAS DOWN-HOLE LOG)":                 "other",
        "OBSERVATION":                                                          "other",
        "STRATIGRAPHIC TEST":                                                   "other",
        "STRATIGRAPHIC TEST, NON OIL/GAS RELATED (HAS DOWN-HOLE LOG)":         "other",
        "DRY HOLE":                                                             "other",
        "UNKNOWN WELL TYPE":                                                    "other",
    },
    field_map={
        "lat":       ["LATITUDE", "_lat"],
        "lon":       ["LONGITUDE", "_lon"],
        "depth_ft":  ["TOTAL_DPTH"],
        "operator":  ["OPERATOR"],
        "status":    ["STATUS"],
        "well_type": ["WELL_TYPE"],
        "api":       ["API_NUMBER"],
        "county":    ["COUNTY"],
        "spud_date": ["SPUD_DATE"],
    },
)


class MOAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Prefer attribute lat/lon; fall back to geometry-injected _lat/_lon
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
        # Strip the dash so normalize_api gets a plain digit string
        api_clean = api_raw.replace("-", "")

        depth_raw = row.get("TOTAL_DPTH")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # SPUD_DATE is epoch milliseconds
        spud_ms = row.get("SPUD_DATE")
        spud_date = ""
        if spud_ms:
            try:
                dt = datetime.fromtimestamp(int(spud_ms) / 1000, tz=timezone.utc)
                if dt.year >= 1850:
                    spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        status_raw = str(row.get("STATUS") or "").strip()
        status = cfg.resolve_status(status_raw)

        well_type_raw = str(row.get("WELL_TYPE") or "").strip()
        well_type = cfg.resolve_well_type(well_type_raw)

        operator = str(row.get("OPERATOR") or "Unknown").strip() or "Unknown"
        county = str(row.get("COUNTY") or "Unknown").strip() or "Unknown"

        well_id = f"mo-{normalize_api(api_clean)}" if api_clean else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "MO",
            "source": "mo-dnr",
            "well_type": well_type,
        }


adapter = MOAdapter(_config)
