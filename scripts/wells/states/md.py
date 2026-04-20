"""
Maryland — MDE Oil & Gas Wells (FracTracker Alliance / Maryland Dept of Environment)

Source: Maryland Department of Environment via FracTracker Alliance ArcGIS services
  MD_06292017 (obtained from MDE, June 2017):
    Layer 0 — Historical gas wells (~117 wells)
    Layer 1 — Active gas wells    (~10 wells)
  MD_03162015 (obtained from MDE, March 2015):
    Layer 0 — Licensed/permitted wells (~57 wells)

Maryland has very limited oil/gas production, concentrated in the western panhandle
(Garrett and Allegany counties). Total ~180 unique wells.
Geometry is fetched in WGS84 (outSR=4326).
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import is_in_bounds, parse_spud_date

# MD_06292017: historical + active gas wells (from MDE, June 2017)
_SVC_2017 = (
    "https://services.arcgis.com/jDGuO8tYggdCCnUJ"
    "/arcgis/rest/services/MD_06292017/FeatureServer"
)
# MD_03162015: licensed/permitted wells (from MDE, March 2015)
_SVC_2015 = (
    "https://services.arcgis.com/jDGuO8tYggdCCnUJ"
    "/arcgis/rest/services/MD_03162015/FeatureServer"
)

_PAGE_SIZE = 1000

# MD sitecounty abbreviations (from MD_03162015 layer)
_MD_COUNTY = {
    "AL": "Allegany",
    "AN": "Anne Arundel",
    "BA": "Baltimore City",
    "BC": "Baltimore County",
    "CA": "Calvert",
    "CL": "Cecil",
    "CH": "Charles",
    "DO": "Dorchester",
    "FR": "Frederick",
    "GA": "Garrett",
    "HA": "Harford",
    "HO": "Howard",
    "KE": "Kent",
    "MO": "Montgomery",
    "PG": "Prince Georges",
    "QA": "Queen Annes",
    "SM": "St. Marys",
    "SO": "Somerset",
    "TA": "Talbot",
    "WA": "Washington",
    "WI": "Wicomico",
    "WO": "Worcester",
}

_config = BaseConfig(
    state="MD",
    source_label="md-dnr",
    url=_SVC_2017,
    bounds=(37.9, 39.7, -79.5, -75.0),
    output=Path("public/data/wells-md.json"),
    raw_dir=Path("data/raw/md"),
    require_depth=False,
    status_map={
        "PLUGGED":              "Plugged & Abandoned",
        "PLUGGED AND ABANDONED":"Plugged & Abandoned",
        "P&A":                  "Plugged & Abandoned",
        "ACTIVE":               "Active",
        "PRODUCING":            "Active",
        "SHUT IN":              "Inactive",
        "SHUT-IN":              "Inactive",
        "DRY":                  "Plugged & Abandoned",
        "DRY HOLE":             "Plugged & Abandoned",
        "PERMITTED":            "Permitted",
        "ISSUED":               "Permitted",
    },
    well_type_map={
        "GAS":          "gas",
        "OIL":          "oil",
        "OIL AND GAS":  "oil",
        "STORAGE":      "injection",
        "INJECTION":    "injection",
        "DISPOSAL":     "disposal",
        "OTHER":        "other",
    },
)


def _fetch_layer(service_url: str, layer_id: int, out_jsonl: Path, tag: str) -> int:
    """Paginate one FeatureServer layer; append JSON lines to out_jsonl. Returns count."""
    url = f"{service_url}/{layer_id}/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": _PAGE_SIZE,
    }
    offset = 0
    total = 0

    with open(out_jsonl, "a") as fh:
        while True:
            params["resultOffset"] = offset
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            features = data.get("features", [])
            if not features:
                break

            for feat in features:
                attrs = dict(feat.get("attributes", {}))
                geom = feat.get("geometry") or {}
                attrs["_lat"] = geom.get("y")
                attrs["_lon"] = geom.get("x")
                attrs["_tag"] = tag          # "hist", "active", or "licensed"
                fh.write(json.dumps(attrs) + "\n")

            total += len(features)
            if not data.get("exceededTransferLimit", False) and len(features) < _PAGE_SIZE:
                break
            offset += len(features)

    return total


class MDAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "md_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        out.write_text("")  # create / truncate

        layers = [
            (_SVC_2017, 0, "hist"),     # MD_06292017 layer 0 — historical gas wells
            (_SVC_2017, 1, "active"),   # MD_06292017 layer 1 — active gas wells
            (_SVC_2015, 0, "licensed"), # MD_03162015 layer 0 — licensed/permitted wells
        ]
        grand_total = 0
        for svc, layer_id, tag in layers:
            svc_short = svc.split("/services/")[-1].split("/")[0]
            print(f"  Fetching {svc_short} layer {layer_id} ({tag}) ...")
            n = _fetch_layer(svc, layer_id, out, tag)
            print(f"    → {n:,} features")
            grand_total += n

        print(f"  Downloaded {grand_total:,} total features → {out}")
        return out

    def parse(self, raw: Path) -> Iterator[dict]:
        with open(raw, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config
        tag = row.get("_tag", "")

        try:
            lat = float(row.get("_lat") or 0)
            lon = float(row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # --- Status ---
        if tag == "hist":
            # MD_06292017 layer 0 fields: Status
            status_raw = str(row.get("Status") or "").strip().upper()
        elif tag == "active":
            # MD_06292017 layer 1: no explicit status field → treat as Active
            status_raw = "ACTIVE"
        else:
            # MD_03162015 layer 0: no status field → treat as Permitted/licensed
            status_raw = "PERMITTED"
        status = cfg.resolve_status(status_raw) if status_raw else "Unknown"

        # --- Depth ---
        depth_raw = row.get("Depth") or row.get("Well_Depth") or row.get("welldepth") or 0
        try:
            depth_ft = int(float(str(depth_raw).replace(",", "")))
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # --- Spud / drill date ---
        # MD_06292017 layer 0: Date_drill stored as "MM/DD/YYYY" (may have stray spaces)
        # MD_03162015 layer 0: perexpire is a permit expiry epoch-ms — not a spud date, skip it
        date_raw = row.get("Date_drill") or ""
        spud_date = ""
        if date_raw:
            # Collapse internal whitespace then delegate to shared parser
            cleaned = re.sub(r"\s+", "", str(date_raw).strip())
            # Reinsert "/" separators if they were collapsed: "07/01/1951" stays intact
            spud_date = parse_spud_date(cleaned)

        # --- Operator ---
        operator = (
            str(row.get("Permittee") or row.get("name") or "Unknown").strip()
            or "Unknown"
        )

        # --- Well type: all MD production is gas ---
        well_type = "gas"

        # --- County ---
        county_abbr = str(row.get("sitecounty") or "").strip().upper()
        county = _MD_COUNTY.get(county_abbr, county_abbr.title() if county_abbr else "Unknown")

        # --- ID: prefer permit number ---
        permit = (
            str(row.get("Permit_Num") or row.get("permit") or row.get("lic_no") or "").strip()
        )
        well_id = f"md-{permit}" if permit else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "MD",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = MDAdapter(_config)
