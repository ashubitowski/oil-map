"""
New York — NY DEC Well Data (CSV)

Source: NY Department of Environmental Conservation
  https://www.dec.ny.gov/fs/data/wellDOS.zip
  ~47k wells. Updated nightly.

Fields used:
  API_WellNo, Surface_Longitude, Surface_latitude, Well_Status,
  True_vertical_depth, Company_name, Date_Spudded, Well_Type, County
"""

import csv
import io
import zipfile
from pathlib import Path
from typing import Iterator, Optional
from urllib.request import urlopen

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds, parse_spud_date

_URL = "https://www.dec.ny.gov/fs/data/wellDOS.zip"

_config = BaseConfig(
    state="NY",
    source_label="ny-dec",
    url=_URL,
    bounds=(40.4, 45.1, -79.8, -71.8),
    output=Path("public/data/wells-ny.json"),
    raw_dir=Path("data/raw/ny"),
    require_depth=False,
    status_map={
        # Well_Status codes from NY DEC
        "AC": "Active",          # Active
        "CO": "Active",          # Completed
        "TR": "Active",          # Test results
        "SI": "Inactive",        # Shut In
        "IN": "Inactive",        # Inactive
        "UL": "Inactive",        # Unplugged (legacy)
        "UM": "Inactive",        # Unplugged migrated
        "UN": "Inactive",        # Unplugged
        "RE": "Inactive",        # Returned
        "RW": "Inactive",        # Returned / withdrawn
        "NR": "Inactive",        # Not reported
        "EX": "Inactive",        # Expired
        "CA": "Inactive",        # Cancelled
        "DD": "Inactive",        # Drilled dry
        "PA": "Plugged & Abandoned",
        "PB": "Plugged & Abandoned",  # Plugged - bonded
        "DC": "Plugged & Abandoned",  # Decommissioned
        "VP": "Permitted",       # Valid permit
        "PM": "Permitted",       # Permit
        "CONFIDENTIAL": "Unknown",
    },
    well_type_map={
        # Well_Type codes from NY DEC
        "OD": "oil",             # Oil / development
        "OW": "oil",             # Oil well
        "OE": "oil",             # Oil / exploratory
        "GD": "gas",             # Gas / development
        "GW": "gas",             # Gas well
        "GE": "gas",             # Gas / exploratory
        "SG": "gas",             # Storage gas
        "IW": "injection",       # Injection well
        "DW": "disposal",        # Disposal well
        "DS": "disposal",        # Disposal (salt)
        "BR": "other",           # Brine
        "NL": "other",           # Not listed
        "DH": "other",           # Dry hole
        "ST": "other",           # Stratigraphic test
        "MS": "other",           # Miscellaneous
        "MM": "other",           # Miscellaneous / multiple
        "TH": "other",           # Thermal
        "MB": "other",           # Monitoring / brine
        "LP": "other",           # Low pressure
        "CONFIDENTIAL": "other",
    },
)


class NYAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        dest = cfg.raw_dir / "wellDOS.zip"
        if dest.exists():
            print(f"  Using cached {dest} (delete to re-download)")
            return dest
        print(f"  Downloading {_URL} ...")
        with urlopen(_URL, timeout=120) as r:
            data = r.read()
        dest.write_bytes(data)
        print(f"  Saved {len(data) / 1e6:.1f} MB → {dest}")
        return dest

    def parse(self, raw: Path) -> Iterator[dict]:
        with zipfile.ZipFile(raw) as zf:
            with zf.open("wellspublic.csv") as f:
                text = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                reader = csv.DictReader(text)
                count = 0
                for row in reader:
                    count += 1
                    yield row
                print(f"  CSV: {count:,} records")

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("Surface_latitude") or 0)
            lon = float(row.get("Surface_Longitude") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_WellNo") or "").strip()
        if not api_raw:
            return None

        depth_raw = row.get("True_vertical_depth") or ""
        try:
            depth_ft = int(float(str(depth_raw).strip())) if str(depth_raw).strip() else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 35000:
            depth_ft = 0

        spud_raw = str(row.get("Date_Spudded") or "").strip()
        # NY dates arrive as "YYYY-MM-DD HH:MM:SS" — take just the date part
        if spud_raw and " " in spud_raw:
            spud_raw = spud_raw.split(" ")[0]
        spud_date = parse_spud_date(spud_raw)

        status_raw = str(row.get("Well_Status") or "").strip().upper()
        status = cfg.resolve_status(status_raw)

        well_type_raw = str(row.get("Well_Type") or "").strip().upper()
        well_type = cfg.resolve_well_type(well_type_raw)

        operator = str(row.get("Company_name") or "Unknown").strip() or "Unknown"
        county = str(row.get("County") or "Unknown").strip() or "Unknown"
        if county == "Statewide":
            county = "Unknown"

        return {
            "id": f"ny-{normalize_api(api_raw)}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "NY",
            "source": "ny-dec",
            "well_type": well_type,
        }


adapter = NYAdapter(_config)
