"""
New Mexico — OCD wells via NM State Land Office ArcGIS MapServer.

Source: NM Oil Conservation Division / Energy, Minerals & Natural Resources Dept
  Service: https://mapservice.nmstatelands.org/arcgis/rest/services/Public/NMOCD_Wells_V3/MapServer/5
  Verified 2026-04 — returns JSON with latitude/longitude attributes directly

~35k wells; Permian Basin (SE) + San Juan Basin (NW).
"""

from pathlib import Path
from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig

NM_MAP_SERVER = "https://mapservice.nmstatelands.org/arcgis/rest/services/Public/NMOCD_Wells_V3/MapServer/5"

_config = BaseConfig(
    state="NM",
    source_label="nm-ocd",
    url=NM_MAP_SERVER,
    bounds=(31.3, 37.1, -109.1, -103.0),
    output=Path("public/data/wells-nm.json"),
    raw_dir=Path("data/raw/nm"),
    status_map={
        "Active": "Active", "Inactive": "Inactive", "Plugged": "Plugged & Abandoned",
        "Cancelled": "Inactive", "Permitted": "Permitted",
        "A": "Active", "I": "Inactive", "P": "Plugged & Abandoned",
    },
    well_type_map={
        "Oil": "oil", "OIL": "oil", "O": "oil",
        "Gas": "gas", "GAS": "gas", "G": "gas",
        "Oil and Gas": "oil-gas", "OIL AND GAS": "oil-gas", "OG": "oil-gas",
        "Water": "injection", "Injection": "injection", "INJ": "injection",
        "Disposal": "disposal", "WD": "disposal",
        "Dry Hole": "other", "Other": "other",
    },
    field_map={
        # This service stores lat/lon as attributes (not only geometry)
        "lat": ["latitude", "LATITUDE", "lat", "LAT"],
        "lon": ["longitude", "LONGITUDE", "lon", "LON"],
        "depth_ft": ["meas_depth", "MEAS_DEPTH", "true_verti", "TRUE_VERTI",
                     "TOTAL_DEPTH", "TD_FT", "DEPTH"],
        "api": ["API", "api", "API_NUMBER", "API_NO"],
        "operator": ["operator", "OPERATOR", "operator_n", "OPERATOR_N", "OPERATOR_NAME"],
        "status": ["status", "STATUS", "WELL_STATUS"],
        "well_type": ["type", "TYPE", "WELL_TYPE", "well_type"],
        "county": ["county", "COUNTY", "COUNTY_NAME"],
        "spud_date": ["spud_date", "SPUD_DATE", "SPUD"],
    },
)

adapter = ArcGISAdapter(_config)
