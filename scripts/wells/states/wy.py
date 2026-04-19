"""
Wyoming — WOGCC wells via Wyoming Geospatial Hub (ArcGIS).

Source: Wyoming Oil and Gas Conservation Commission
  Hub: https://data.geospatialhub.org/datasets/46d3629e4e3b4ef6978cb5e6598f97bb_0
  Verified 2026-04

The Hub dataset maps to an ArcGIS FeatureServer. Use the ArcGIS Hub CSV
download API which returns the full dataset with lat/lon included.
~30k wells; Powder River Basin cluster in NE Wyoming.
"""

from pathlib import Path
from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig

# Wyoming Geospatial Hub item ID: 46d3629e4e3b4ef6978cb5e6598f97bb (verified 2026-04)
# Actual MapServer URL resolved from Hub metadata
WY_FEATURE_SERVER = "https://services.wygisc.org/HostGIS/rest/services/GeoHub/WOGCCActiveWells/MapServer/0"

_config = BaseConfig(
    state="WY",
    source_label="wy-wogcc",
    url=WY_FEATURE_SERVER,
    bounds=(41.0, 45.1, -111.1, -104.1),
    output=Path("public/data/wells-wy.json"),
    raw_dir=Path("data/raw/wy"),
    status_map={
        "AI": "Active",
        "FL": "Active",
        "GL": "Active",
        "PG": "Active",
        "PO": "Active",
        "PL": "Active",
        "PH": "Active",
        "EP": "Active",
        "DP": "Active",
        "WS": "Active",
        "WP": "Active",
        "WD": "Active",
        "MW": "Active",
        "ACTIVE": "Active",
        "SI": "Inactive",
        "NI": "Inactive",
        "SO": "Inactive",
        "SP": "Inactive",
        "TA": "Inactive",
        "NR": "Inactive",
        "INACTIVE": "Inactive",
        "PA": "Plugged & Abandoned",
        "PR": "Plugged & Abandoned",
        "PS": "Plugged & Abandoned",
        "SR": "Plugged & Abandoned",
        "DH": "Plugged & Abandoned",
        "DR": "Plugged & Abandoned",
        "PLUGGED & ABANDONED": "Plugged & Abandoned",
        "AP": "Permitted",
        "UK": "Unknown",
    },
    well_type_map={
        "O": "oil", "G": "gas", "I": "injection",
        "S": "disposal", "D": "other", "LW": "other",
        "M": "other", "NA": "other",
    },
    field_map={
        "lat": ["LATITUDE"],
        "lon": ["LONGITUDE"],
        "depth_ft": ["TD", "TOTAL_DEPTH", "TD_FT", "DEPTH", "PLUG_BACK"],
        "api": ["API_NUMBER", "APINO"],
        "operator": ["COMPANY", "OPCO"],
        "status": ["STATUS"],
        "well_type": ["WELL_CLASS"],
        "county": ["COUNTY"],
        "spud_date": ["SPUD"],
    },
)

adapter = ArcGISAdapter(_config)
