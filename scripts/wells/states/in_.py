"""
Indiana — DNR Division of Oil and Gas Wells (ArcGIS FeatureServer)

Source: Indiana DNR Oil and Gas Wells (public layer, gisdata.in.gov)
  https://gisdata.in.gov/server/rest/services/Hosted/OilAndGasWells/FeatureServer/0
  ~78k wells. Note: the newer Oil_and_Gas_Wells_RO service has richer fields
  but requires an authenticated token; this public layer is used instead.

Fields used:
  geometry (x/y) — WGS84 surface coords
  county         — county name
  status         — well status string
  igs_id         — Indiana Geological Survey well ID (used as well ID)
  igsz           — zero-padded IGS ID (6 chars)
  classii        — Class II injection flag (1 = injection)

Note: this dataset lacks depth, operator, spud_date, and well_type.
"""

from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import is_in_bounds

_URL = "https://gisdata.in.gov/server/rest/services/Hosted/OilAndGasWells/FeatureServer/0"

_config = BaseConfig(
    state="IN",
    source_label="in-dnr",
    url=_URL,
    bounds=(37.7, 41.8, -88.1, -84.8),
    output=Path("public/data/wells-in.json"),
    raw_dir=Path("data/raw/in"),
    require_depth=False,
    status_map={
        # Active
        "ACTIVE":            "Active",
        "DRILLING":          "Active",
        "REVINJ NPAS&FV":    "Active",   # RevInj NPaS&FV
        # Inactive / temporarily abandoned
        "INACTIVE":          "Inactive",
        "OTHER INACTIVE":    "Inactive",
        "TA":                "Inactive",  # temporarily abandoned
        # Plugged & Abandoned variants
        "PLUGGED":           "Plugged & Abandoned",
        "PLUGD & ABANDND":   "Plugged & Abandoned",
        "INADQTLY PLGGD":    "Plugged & Abandoned",  # inadequately plugged
        "PRSMD PLGGD":       "Plugged & Abandoned",  # presumed plugged
        "PRSMD PLGGD (I)":   "Plugged & Abandoned",
        "PRSMD PLGGD(I)":    "Plugged & Abandoned",
        # Unknown / cancelled / not drilled
        "CANCELLED":         "Unknown",
        "EXPIRED":           "Unknown",
        "NOT DRILLED":       "Unknown",
        "ORPHANED":          "Unknown",
        "REVOKED":           "Unknown",
    },
    # Well type is inferred from classii flag; no well_type field in source.
    well_type_map={},
    field_map={
        "lat":    ["_lat"],
        "lon":    ["_lon"],
        "county": ["county"],
        "status": ["status"],
    },
)


class INAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("_lat") or 0)
            lon = float(row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        igs_raw = str(row.get("igsz") or row.get("igs_id") or "").strip()
        well_id = f"in-{igs_raw}" if igs_raw else None

        status_raw = str(row.get("status") or "").strip().upper()
        status = cfg.status_map.get(status_raw, "Unknown")

        county = str(row.get("county") or "Unknown").strip() or "Unknown"

        # Infer well_type from Class II injection flag
        classii = row.get("classii")
        try:
            is_injection = int(classii) == 1
        except (TypeError, ValueError):
            is_injection = False
        well_type = "injection" if is_injection else "other"

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": 0,
            "operator": "Unknown",
            "spud_date": "",
            "status": status,
            "county": county,
            "state": "IN",
            "source": "in-dnr",
            "well_type": well_type,
        }


adapter = INAdapter(_config)
