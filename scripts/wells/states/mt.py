"""
Montana — MBOGC Well Surface Locations (shapefile)

Source: Montana Board of Oil and Gas Conservation GIS Data Files
  https://bogfiles.dnrc.mt.gov/GISData/WellSurface/YYYYMMDD_wells.zip
  ~42k wells. Updated periodically; URL contains date.

Requires: pip install pyshp
"""

import datetime
import io
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator, Optional

try:
    import shapefile
except ImportError:
    sys.exit("pyshp not installed. Run: pip install pyshp")

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds, parse_spud_date

_BASE = "https://bogfiles.dnrc.mt.gov/GISData/WellSurface"
_LOOK_BACK_DAYS = 60

# API state code 25 = Montana; 3-digit county code follows
_MT_COUNTY = {
    "001": "Beaverhead", "003": "Big Horn", "005": "Blaine", "007": "Broadwater",
    "009": "Carbon", "011": "Carter", "013": "Cascade", "015": "Chouteau",
    "017": "Custer", "019": "Daniels", "021": "Dawson", "023": "Deer Lodge",
    "025": "Fallon", "027": "Fergus", "029": "Flathead", "031": "Gallatin",
    "033": "Garfield", "035": "Glacier", "037": "Golden Valley", "039": "Granite",
    "041": "Hill", "043": "Jefferson", "045": "Judith Basin", "047": "Lake",
    "049": "Lewis And Clark", "051": "Liberty", "053": "Lincoln", "055": "Madison",
    "057": "Mccone", "059": "Meagher", "061": "Mineral", "063": "Missoula",
    "065": "Musselshell", "067": "Park", "069": "Petroleum", "071": "Phillips",
    "073": "Pondera", "075": "Powder River", "077": "Powell", "079": "Prairie",
    "081": "Ravalli", "083": "Richland", "085": "Roosevelt", "087": "Rosebud",
    "089": "Sanders", "091": "Sheridan", "093": "Silver Bow", "095": "Stillwater",
    "097": "Sweet Grass", "099": "Teton", "101": "Toole", "103": "Treasure",
    "105": "Valley", "107": "Wheatland", "109": "Wibaux", "111": "Yellowstone",
}

_config = BaseConfig(
    state="MT",
    source_label="mt-bogc",
    url=_BASE,
    bounds=(44.3, 49.1, -116.1, -104.0),
    output=Path("public/data/wells-mt.json"),
    raw_dir=Path("data/raw/mt"),
    require_depth=False,
    status_map={
        "PRODUCING":                "Active",
        "ACTIVE INJECTION":         "Active",
        "COMPLETED":                "Active",
        "SPUDDED":                  "Active",
        "PERMIT TO DRILL":          "Permitted",
        "PERMITTED INJECTION WELL": "Permitted",
        "SHUT IN":                  "Inactive",
        "TEMPORARILY ABANDONED":    "Inactive",
        "DOMESTIC":                 "Inactive",
        "WATER WELL, RELEASED":     "Inactive",
        "P&A - APPROVED":           "Plugged & Abandoned",
        "ABANDONED":                "Plugged & Abandoned",
        "ABANDONED - UNAPPROVED":   "Plugged & Abandoned",
        "EXPIRED, NOT RELEASED":    "Unknown",
        "UNKNOWN":                  "Unknown",
    },
    well_type_map={
        "OIL":               "oil",
        "GAS":               "gas",
        "COAL BED METHANE":  "gas",
        "INJECTION, EOR":    "injection",
        "INJECTION, INDIAN LANDS": "injection",
        "INJECTION - DISPOSAL": "disposal",
        "GAS STORAGE":       "other",
        "DRY HOLE":          "other",
        "STRATIGRAPHIC TEST":"other",
        "WATER SOURCE":      "other",
    },
)


def _find_zip_url() -> str:
    """Probe back from today to find the latest dated shapefile ZIP."""
    today = datetime.date.today()
    for delta in range(_LOOK_BACK_DAYS):
        d = today - datetime.timedelta(days=delta)
        fname = f"{d.year}{d.month:02d}{d.day:02d}_wells.zip"
        url = f"{_BASE}/{fname}"
        try:
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=8)
            return url
        except Exception:
            continue
    raise RuntimeError(f"No MT wells ZIP found in the last {_LOOK_BACK_DAYS} days")


class MTAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        dest = cfg.raw_dir / "mt_wells.zip"
        if dest.exists():
            print(f"  Using cached {dest} (delete to re-download)")
            return dest
        url = _find_zip_url()
        print(f"  Downloading {url} ...")
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        dest.write_bytes(data)
        print(f"  Saved {len(data) / 1e6:.1f} MB → {dest}")
        return dest

    def parse(self, raw: Path) -> Iterator[dict]:
        with zipfile.ZipFile(raw) as zf:
            sf = shapefile.Reader(
                shp=io.BytesIO(zf.read("wells.shp")),
                dbf=io.BytesIO(zf.read("wells.dbf")),
                shx=io.BytesIO(zf.read("wells.shx")),
                encoding="latin-1",
            )
            fields = [f[0] for f in sf.fields[1:]]
            count = 0
            for sr in sf.iterShapeRecords():
                row = dict(zip(fields, sr.record))
                if sr.shape.shapeType != 0 and hasattr(sr.shape, "points") and sr.shape.points:
                    row["_lon"], row["_lat"] = sr.shape.points[0]
                count += 1
                yield row
            print(f"  Shapefile: {count:,} records")

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

        api_raw = str(row.get("API_WellNo") or "").strip()
        county_code = api_raw[2:5] if len(api_raw) >= 5 else ""
        county = _MT_COUNTY.get(county_code, "Unknown")

        depth_raw = row.get("DTD")
        try:
            depth_ft = int(depth_raw) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 35000:
            depth_ft = 0

        completed_raw = str(row.get("Completed") or "").strip()
        spud_date = parse_spud_date(completed_raw)

        status = cfg.resolve_status((row.get("Status") or "").strip().upper())
        well_type = cfg.resolve_well_type((row.get("Type") or "").strip().upper())
        operator = str(row.get("CoName") or "Unknown").strip() or "Unknown"

        return {
            "id": f"mt-{normalize_api(api_raw)}" if api_raw else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "MT",
            "source": "mt-bogc",
            "well_type": well_type,
        }


adapter = MTAdapter(_config)
