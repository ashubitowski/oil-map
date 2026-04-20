"""
Arkansas — AOGC (Oil and Gas Commission) Wells

Source: Arkansas GIS ArcGIS FeatureServer
  https://gis.arkansas.gov/arcgis/rest/services/FEATURESERVICES/Utilities/FeatureServer/5
  ~38k wells.

Fields used:
  coordinates_latitude / coordinates_longitude  — decimal degree coords
  depthbottom                                   — depth (ft)
  operatorname                                  — operator
  wellstatus                                    — status code
  welltype                                      — well type code
  countyname                                    — county
  permitnumberstring                            — permit number (used as id)
  wellid                                        — unique well identifier
"""

from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import is_in_bounds

_URL = "https://gis.arkansas.gov/arcgis/rest/services/FEATURESERVICES/Utilities/FeatureServer/5"

_config = BaseConfig(
    state="AR",
    source_label="ar-aogc",
    url=_URL,
    bounds=(33.0, 36.5, -94.6, -89.6),
    output=Path("public/data/wells-ar.json"),
    raw_dir=Path("data/raw/ar"),
    require_depth=False,
    status_map={
        # Active / Producing
        "A":   "Active",
        "PR":  "Active",    # Producing
        "SI":  "Active",    # Shut-In (still active infrastructure)
        "SP":  "Active",    # Spudded (drilling underway)
        # Inactive
        "IN":  "Inactive",  # Inactive - Not TA
        "TA":  "Inactive",  # Temporarily Abandoned
        "C":   "Inactive",  # Completed (not yet producing/plugged)
        "DW":  "Inactive",  # Domestic Well - Gas
        "RW":  "Inactive",  # Released - Water Well
        # Plugged & Abandoned
        "PA":  "Plugged & Abandoned",
        "DA":  "Plugged & Abandoned",   # Dry And Abandoned
        "AOW": "Plugged & Abandoned",   # Abandoned/Orphaned Well
        # Permitted
        "PW":  "Permitted",
        "PWI": "Permitted",             # Injection Permit Issued
        # Unknown / expired
        "EX":  "Unknown",               # Expired Permit
        "ex":  "Unknown",               # same, different case in source
        "UN":  "Unknown",
    },
    well_type_map={
        "OIL":  "oil",
        "GAS":  "gas",
        "CBM":  "gas",          # Coal Bed Methane
        "EOR":  "injection",    # Enhanced Oil Recovery
        "SWD":  "disposal",     # Salt Water Disposal
        "SWI":  "injection",    # Salt Water Injection
        "BIW":  "injection",    # Brine Injection Well
        "GI":   "injection",    # Gas Injector
        "GS":   "other",        # Gas Storage
        "BSW":  "other",        # Brine Supply Well
        "WS":   "other",        # Water Supply
        "WDW":  "other",        # Waste Disposal Well
        "CBMS": "other",        # Coal Bed Methane Service Well
        "SEX":  "other",        # Seismic-Exploratory Well
        "SW":   "other",        # Service Well
        "EXP":  "other",        # Expired Permit (type slot)
        "ISC":  "other",        # Need Code
        "UN":   "other",        # Unknown
    },
    field_map={
        "lat":      ["coordinates_latitude", "_lat"],
        "lon":      ["coordinates_longitude", "_lon"],
        "depth_ft": ["depthbottom"],
        "operator": ["operatorname"],
        "status":   ["wellstatus"],
        "well_type":["welltype"],
        "county":   ["countyname"],
        "api":      ["permitnumberstring"],
    },
)


class ARAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("coordinates_latitude") or row.get("_lat") or 0)
            lon = float(row.get("coordinates_longitude") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        depth_raw = row.get("depthbottom")
        try:
            depth_ft = int(depth_raw) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        status = cfg.resolve_status(str(row.get("wellstatus") or "").strip())
        well_type = cfg.resolve_well_type(str(row.get("welltype") or "").strip())
        operator = str(row.get("operatorname") or "Unknown").strip() or "Unknown"
        county = str(row.get("countyname") or "Unknown").strip().title() or "Unknown"

        # Use wellid as stable unique identifier; fall back to permit number
        well_id = str(row.get("wellid") or "").strip()
        permit = str(row.get("permitnumberstring") or "").strip()
        if well_id:
            record_id = f"ar-{well_id}"
        elif permit:
            record_id = f"ar-{permit}"
        else:
            return None  # no usable id

        return {
            "id": record_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": "",
            "status": status,
            "county": county,
            "state": "AR",
            "source": "ar-aogc",
            "well_type": well_type,
        }


adapter = ARAdapter(_config)
