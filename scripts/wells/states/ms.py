"""
Mississippi — Mississippi Oil and Gas Board (OGB) Well Shapefile

Source: Mississippi OGB bulk shapefile download
  https://www.ogb.state.ms.us/downloads.php
  ~25k wells. Updated daily; URL contains date.

Fields used (wells_otherfields shapefile):
  API         — API number
  type        — well type code (OIL, GAS, DH, SWD, EOR, …)
  status      — status code (PR, PA, CI, AI, TA, …)
  CountyName  — county name
  PermitDate  — permit / spud date
  TD          — total depth (ft)
  geometry    — point coordinates (lon, lat)

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

_BASE = "https://www.ogb.state.ms.us/Downloads/WellShapeFiles"
_LOOK_BACK_DAYS = 14

_config = BaseConfig(
    state="MS",
    source_label="ms-ogb",
    url=_BASE,
    bounds=(30.1, 35.0, -91.7, -88.1),
    output=Path("public/data/wells-ms.json"),
    raw_dir=Path("data/raw/ms"),
    require_depth=False,
    status_map={
        # Active / producing
        "PR":    "Active",       # Producing
        "AI":    "Active",       # Active Injection
        "CPL":   "Active",       # Completed (Form 3 recv'd) Producing
        "DG":    "Active",       # Disposal/Gas active
        "DGW":   "Active",       # Disposal/Gas well active
        "I":     "Active",       # Injection active
        "PO":    "Active",       # Producing Oil
        # Inactive / shut-in
        "CI":    "Inactive",     # Closed In (Producing Well)
        "SB":    "Inactive",     # Stand By (Injection Well)
        "TA":    "Inactive",     # Temporarily Abandoned
        "NRR":   "Inactive",     # No Report Required
        "CPLNP": "Inactive",     # Completed Not Producing
        "CA":    "Inactive",     # Closed Awaiting
        "DWW":   "Inactive",     # Disposal Water Well (idle)
        "PWI":   "Inactive",     # Permit Well - Inactive
        "PW":    "Inactive",     # Permit Well
        "PWP":   "Inactive",     # Permit Well - Pending
        "LEACH": "Inactive",     # Leach well
        # Plugged & Abandoned
        "PA":    "Plugged & Abandoned",    # Plugged and Abandoned
        "PAS":   "Plugged & Abandoned",    # Plugged and Abandoned - surveyor inspection
        "DA":    "Plugged & Abandoned",    # Dry and Abandoned
        "OPA":   "Plugged & Abandoned",    # Orphaned P&A
        "APA":   "Plugged & Abandoned",    # Appears P&A / No Records
        "APS":   "Plugged & Abandoned",    # Appears P&A - surveyor inspection
        "AA":    "Plugged & Abandoned",    # Intent to Abandon Approved
        "JA":    "Plugged & Abandoned",    # Judicially Abandoned
        "O":     "Plugged & Abandoned",    # Orphaned Well
        "EX":    "Plugged & Abandoned",    # Expired/Abandoned
        "AU":    "Plugged & Abandoned",    # Abandoned Unplugged
        "AUS":   "Plugged & Abandoned",    # Abandoned Unplugged - surveyor
    },
    well_type_map={
        "OIL": "oil",
        "GAS": "gas",
        "CO2": "gas",
        "DH":  "other",       # Dry Hole
        "SWD": "disposal",    # Salt Water Disposal
        "EOR": "injection",   # Enhanced Oil Recovery Injection
        "BDW": "disposal",    # Brine Disposal Well
        "WS":  "other",       # Water Source
        "MON": "other",       # Monitor / Observation
        "GSR": "other",       # Gas Storage Reservoir
    },
)


def _find_zip_url() -> str:
    """Probe back from today to find the latest dated shapefile ZIP."""
    today = datetime.date.today()
    for delta in range(_LOOK_BACK_DAYS):
        d = today - datetime.timedelta(days=delta)
        fname = f"{d.year}{d.month:02d}{d.day:02d}_wells_otherfields.zip"
        url = f"{_BASE}/{fname}"
        try:
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=10)
            return url
        except Exception:
            continue
    raise RuntimeError(f"No MS wells ZIP found in the last {_LOOK_BACK_DAYS} days")


class MSAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        dest = cfg.raw_dir / "ms_wells.zip"
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
                shp=io.BytesIO(zf.read("wells_otherfields.shp")),
                dbf=io.BytesIO(zf.read("wells_otherfields.dbf")),
                shx=io.BytesIO(zf.read("wells_otherfields.shx")),
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

        api_raw = str(row.get("API") or "").strip()

        depth_raw = row.get("TD")
        try:
            depth_ft = int(str(depth_raw).strip()) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 35000:
            depth_ft = 0

        # PermitDate comes back as a datetime.date object from pyshp
        permit_date = row.get("PermitDate")
        spud_date = ""
        if permit_date:
            try:
                spud_date = str(permit_date)  # already YYYY-MM-DD from pyshp
            except Exception:
                pass
        if not spud_date:
            spud_date = parse_spud_date("")

        status = cfg.resolve_status((row.get("status") or "").strip())
        well_type = cfg.resolve_well_type((row.get("type") or "").strip().upper())

        # Operator is not in this shapefile — use well display name as fallback
        operator = str(row.get("DispName") or "Unknown").strip() or "Unknown"

        county = str(row.get("CountyName") or "Unknown").strip().title() or "Unknown"

        return {
            "id": f"ms-{normalize_api(api_raw)}" if api_raw else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "MS",
            "source": "ms-ogb",
            "well_type": well_type,
        }


adapter = MSAdapter(_config)
