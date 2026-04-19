"""
BOEM OCS borehole data — Gulf of Mexico (GOM).

Source: Bureau of Ocean Energy Management
  https://www.data.boem.gov/Main/Files/Borehole.zip
  Pipe-delimited; filter REGION_CODE = 'G' for Gulf of Mexico.
"""

import math
from pathlib import Path
from typing import Iterator

from scripts.wells.adapters.direct_download import DirectDownloadAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import col, parse_spud_date

_config = BaseConfig(
    state="GOM",
    source_label="boem",
    url="https://www.data.boem.gov/Main/Files/Borehole.zip",
    bounds=(23.0, 31.0, -98.0, -80.0),
    output=Path("public/data/wells-offshore.json"),
    raw_dir=Path("data/raw/boem"),
    status_map={
        "ACTIVE": "Active",
        "IN PRODUCTION": "Active",
        "PRODUCING": "Active",
        "IDLE": "Inactive",
        "SHUT-IN": "Inactive",
        "SHUT IN": "Inactive",
        "TEMPORARILY ABANDONED": "Inactive",
        "TA": "Inactive",
        "PERMANENTLY ABANDONED": "Plugged & Abandoned",
        "ABANDONED": "Plugged & Abandoned",
        "PLUGGED AND ABANDONED": "Plugged & Abandoned",
        "P&A": "Plugged & Abandoned",
        "APPROVED": "Permitted",
    },
    well_type_map={},
    field_map={
        "lat": ["SURFACE_LATITUDE", "SURF_LAT", "BH_LAT", "LATITUDE", "LAT"],
        "lon": ["SURFACE_LONGITUDE", "SURF_LON", "BH_LON", "LONGITUDE", "LON"],
        "depth_ft": ["TOTAL_DEPTH", "TOTAL_MD_FT", "TOTAL_MEASURED_DEPTH", "TVD_FT", "DEPTH_FT"],
        "api": ["API_WELL_NUMBER", "API_NUMBER", "API", "BOREHOLE_ID", "WELL_NUMBER"],
        "operator": ["COMPANY_NAME", "COMP_NAME", "OPERATOR", "OPERATOR_NAME"],
        "status": ["WELL_STATUS", "BH_STAT", "STATUS"],
        "spud_date": ["SPUD_DATE", "SPUD"],
    },
)


class BOEMAdapter(DirectDownloadAdapter):
    def parse(self, raw: Path) -> Iterator[dict]:
        # BOEM ZIP is pipe-delimited — yield only GOM rows
        for row in super().parse(raw):
            region = col(row, "REGION_CODE", "REGION", "REG_CODE")
            if region.upper() != "G":
                continue
            yield row

    def normalize_row(self, row: dict) -> "Optional[dict]":
        well = super().normalize_row(row)
        if well is None:
            return None

        # BOEM wells use lease/area/block as "county"
        area = col(row, "AREA_CODE", "AREA")
        block = col(row, "BLOCK_NUMBER", "BLOCK_NUM", "BLOCK")
        lease = col(row, "LEASE_NUMBER", "LEASE_NO", "LEASE")
        well["county"] = f"{area} {block}".strip() if (area or block) else (lease or "OCS")
        well["state"] = "GOM"

        # Optional water depth
        water_s = col(row, "WATER_DEPTH", "WATER_DEPTH_FT", "WATERDEPTH")
        try:
            wd = float(water_s)
            if math.isfinite(wd) and wd > 0:
                well["water_depth_ft"] = int(wd)
        except (ValueError, TypeError):
            pass

        return well


adapter = BOEMAdapter(_config)
