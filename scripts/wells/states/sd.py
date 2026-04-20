"""
South Dakota — SD DENR Oil & Gas Program well locations.

Source: South Dakota DENR Oil & Gas Program via ArcGIS FeatureServer
  https://services.arcgis.com/jDGuO8tYggdCCnUJ/arcgis/rest/services/SouthDakotaNEW/FeatureServer/0

Note: The originally suggested URL (arcgis.sd.gov/.../SD_OilGas_Wells/MapServer/0) returns
404 — that service does not exist on the sd.gov ArcGIS server.  The active public service is
the SouthDakotaNEW FeatureServer hosted on arcgis.com (org jDGuO8tYggdCCnUJ).

~512 wells (small dataset; SD oil production is confined to the Williston Basin in the NW corner).
Depth data is frequently absent so require_depth=False.
"""

from pathlib import Path

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig

_config = BaseConfig(
    state="SD",
    source_label="sd-denr",
    url="https://services.arcgis.com/jDGuO8tYggdCCnUJ/arcgis/rest/services/SouthDakotaNEW/FeatureServer/0",
    bounds=(42.4, 45.95, -104.1, -96.4),
    output=Path("public/data/wells-sd.json"),
    raw_dir=Path("data/raw/sd"),
    require_depth=False,
    status_map={
        # Active producing / injecting
        "PRODUCING":                  "Active",
        "INJECTING":                  "Active",
        "SPUDDED":                    "Active",
        # Inactive / suspended
        "SHUT IN":                    "Inactive",
        "TEMPORARILY ABANDONED":      "Inactive",
        "CONVERTED-DOMESTIC GAS":     "Inactive",
        # Plugged & abandoned
        "ABANDONED-NOT REGULATED":    "Plugged & Abandoned",
        # Permitted but not yet drilled
        "NOT SPUDDED":                "Permitted",
    },
    well_type_map={
        "OIL":                  "oil",
        "GAS":                  "gas",
        "SALT WATER DISPOSAL":  "disposal",
        "WATER INJECTION":      "injection",
        "AIR INJECTION":        "injection",
        "GAS INJECTION":        "injection",
        "DRY HOLE":             "other",
        "DRY HOLE-OIL SHOW":    "other",
        "RESERVOIR MONITORING": "other",
        "NONE":                 "other",
        "PENDING":              "other",
    },
    field_map={
        "lat":        ["lat", "_lat"],
        "lon":        ["long_", "_lon"],
        "depth_ft":   ["Total_Depth"],
        "api":        ["API_Number"],
        "operator":   ["Operator"],
        "status":     ["Well_AdminStatus"],
        "well_type":  ["Well_Type_Current"],
        "county":     ["County"],
        "spud_date":  ["Date_Spud"],
    },
)


class SDAdapter(ArcGISAdapter):
    """South Dakota DENR oil & gas wells — thin subclass of ArcGISAdapter."""

    def normalize_row(self, row: dict) -> dict | None:
        # The service provides lat/lon as explicit attributes (already in WGS84)
        # AND as geometry x/y — the parent injects geometry as _lat/_lon.
        # Prefer the attribute lat/long_ when present; fall back to geometry.
        if row.get("lat") and row.get("long_"):
            row.setdefault("_lat", row["lat"])
            row.setdefault("_lon", row["long_"])
        return super().normalize_row(row)


adapter = SDAdapter(_config)
