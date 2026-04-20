"""
Hawaii — USGS NWIS Groundwater / Geothermal Well Sites

Source: U.S. Geological Survey National Water Information System (NWIS)
  https://waterservices.usgs.gov/nwis/site/?stateCd=HI&siteType=GW&format=rdb&siteStatus=all&siteOutput=expanded
  ~600+ well records across all Hawaiian islands.

Hawaii has no oil or gas production. The wells here are:
  - Freshwater/municipal groundwater wells (basal aquifer, volcanic rock)
  - Geothermal exploration boreholes (Kilauea/Puna area, Big Island)
  - Test holes for USGS hydrology research
  - Irrigation wells (sugar cane era)

All are classified as well_type="other" (water / geothermal / monitoring).

Fields used (from USGS NWIS RDB format):
  site_no        — USGS site identifier (used as well ID)
  station_nm     — descriptive site name
  dec_lat_va     — latitude (WGS84 decimal degrees)
  dec_long_va    — longitude (WGS84 decimal degrees)
  well_depth_va  — well depth (feet)
  hole_depth_va  — borehole depth (feet) — used if well_depth_va absent
  construction_dt — YYYYMMDD or YYYY construction/spud date
  nat_aqfr_cd    — national aquifer code (N600HIVLCC = Hawaiian volcanic rock)
  site_tp_cd     — site type (GW, GW-TH = test hole)
  county_cd      — FIPS county code (15001=Hawaii, 15003=Honolulu/Oahu,
                    15005=Kalawao, 15007=Kauai, 15009=Maui)
"""

import io
import sys
from pathlib import Path
from typing import Iterator, Optional

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import is_in_bounds, parse_spud_date

_NWIS_URL = (
    "https://waterservices.usgs.gov/nwis/site/"
    "?stateCd=HI"
    "&siteType=GW"
    "&format=rdb"
    "&siteStatus=all"
    "&siteOutput=expanded"
    "&hasDataTypeCd=gw"
)

# County FIPS → island name
_COUNTY_MAP = {
    "001": "Hawaii",
    "003": "Honolulu",
    "005": "Kalawao",
    "007": "Kauai",
    "009": "Maui",
}

_config = BaseConfig(
    state="HI",
    source_label="hi-dlnr",
    category="water-other",
    url=_NWIS_URL,
    bounds=(18.9, 22.2, -160.2, -154.8),
    output=Path("public/data/wells-hi.json"),
    raw_dir=Path("data/raw/hi"),
    require_depth=False,
    status_map={},
    well_type_map={},
    field_map={},
)


class HIAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        out = cfg.raw_dir / "hi_nwis_sites.rdb"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        print(f"  Fetching USGS NWIS Hawaii groundwater sites ...")
        resp = requests.get(
            "https://waterservices.usgs.gov/nwis/site/",
            params={
                "stateCd": "HI",
                "siteType": "GW",
                "format": "rdb",
                "siteStatus": "all",
                "siteOutput": "expanded",
                "hasDataTypeCd": "gw",
            },
            timeout=120,
        )
        resp.raise_for_status()
        out.write_bytes(resp.content)
        lines = [l for l in resp.text.splitlines() if not l.startswith("#")]
        data_lines = len(lines) - 2  # minus header + format rows
        print(f"  Downloaded {max(data_lines, 0):,} site records → {out}")
        return out

    def parse(self, raw: Path) -> Iterator[dict]:
        """Parse USGS NWIS RDB (tab-separated) format into row dicts."""
        text = raw.read_text(encoding="utf-8")
        lines = text.splitlines()

        # Strip comment lines (start with #)
        data_lines = [l for l in lines if not l.startswith("#")]
        if len(data_lines) < 2:
            return

        # First non-comment line = headers, second = format widths
        headers = data_lines[0].split("\t")
        # data_lines[1] is the format row — skip it
        for line in data_lines[2:]:
            if not line.strip():
                continue
            values = line.split("\t")
            if len(values) != len(headers):
                continue
            yield dict(zip(headers, values))

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("dec_lat_va") or 0)
            lon = float(row.get("dec_long_va") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # Depth: prefer well_depth_va, fall back to hole_depth_va
        depth_ft = 0
        for depth_field in ("well_depth_va", "hole_depth_va"):
            raw_depth = (row.get(depth_field) or "").strip()
            if raw_depth:
                try:
                    d = float(raw_depth)
                    if 0 < d < 40000:
                        depth_ft = int(d)
                        break
                except (TypeError, ValueError):
                    pass

        # Construction date: YYYYMMDD or YYYY (pad to 8 digits)
        construction_raw = (row.get("construction_dt") or "").strip()
        spud_date = ""
        if construction_raw:
            if len(construction_raw) == 4 and construction_raw.isdigit():
                # year only -> YYYY-01-01
                spud_date = f"{construction_raw}-01-01"
            else:
                spud_date = parse_spud_date(construction_raw)

        # Island/county from county FIPS code
        county_fips = (row.get("county_cd") or "").strip().zfill(3)
        county = _COUNTY_MAP.get(county_fips, "Unknown")

        # Well/site type — detect geothermal from station name
        site_tp = (row.get("site_tp_cd") or "").strip()
        station_nm = (row.get("station_nm") or "").strip()
        nm_lower = station_nm.lower()

        if any(k in nm_lower for k in ("geotherm", "thermal", "volcano", "lava", "puna")):
            well_type = "other"  # geothermal
        elif site_tp == "GW-TH":
            well_type = "other"  # test hole
        else:
            well_type = "other"  # all HI wells are non-oil/gas

        # Site ID
        site_no = (row.get("site_no") or "").strip()
        well_id = f"hi-{site_no}" if site_no else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": "USGS",
            "spud_date": spud_date,
            "status": "Unknown",
            "county": county,
            "state": "HI",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = HIAdapter(_config)
