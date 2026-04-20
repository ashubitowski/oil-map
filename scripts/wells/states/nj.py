"""
New Jersey — NJDEP Oil & Natural Gas Exploration Wells (ArcGIS MapServer)

Source: NJ Department of Environmental Protection / Geological and Water Survey
  https://mapsdep.nj.gov/arcgis/rest/services/Features/Geology/MapServer/29
  36 historical exploration wells drilled 1868–1966. None found commercial quantities.

Fields used:
  OBJECTID, COMPANY_NAME, WELL_NAME, COUNTY, MUN, PERMIT_NUM, CNSTR_DATE,
  TOTALDPTH, LATITUDE (DDMMSS), LONGITUDE (DDMMSS)
  Geometry (x/y in WGS84 via outSR=4326) used for coordinates — the
  LATITUDE/LONGITUDE attribute fields are in DDMMSS.SSS format, not decimal degrees.

All wells are historical exploration wells; no active production.
"""

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import is_in_bounds

_SERVICE = (
    "https://mapsdep.nj.gov/arcgis/rest/services/Features/Geology/MapServer/29/query"
)
_PAGE_SIZE = 1000

_config = BaseConfig(
    state="NJ",
    source_label="nj-dep",
    url=_SERVICE,
    bounds=(38.9, 41.4, -75.6, -73.9),
    output=Path("public/data/wells-nj.json"),
    raw_dir=Path("data/raw/nj"),
    require_depth=False,
    status_map={},   # no status field; all are historical plugged/abandoned wells
    well_type_map={},
)


def _parse_depth(raw: str) -> int:
    """Extract numeric feet from strings like '400 ft', '1100+ ft', '3342 ft'."""
    if not raw:
        return 0
    m = re.search(r"(\d+)", str(raw).replace(",", ""))
    if m:
        val = int(m.group(1))
        return val if val <= 35000 else 0
    return 0


def _parse_year(raw: str) -> str:
    """
    Convert CNSTR_DATE strings like '1916', '1919-20', 'before 1868',
    '1921-29' into a YYYY-01-01 date string, or '' if unparseable.
    """
    if not raw:
        return ""
    # Take first 4-digit year found
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", str(raw))
    if m:
        return f"{m.group(1)}-01-01"
    return ""


def _fetch_all(out_jsonl: Path) -> None:
    """Paginate the ArcGIS MapServer and write each feature as a JSON line."""
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    offset = 0
    total_written = 0

    with open(out_jsonl, "w") as fh:
        while True:
            params = urllib.parse.urlencode({
                "where": "1=1",
                "outFields": (
                    "OBJECTID,COMPANY_NAME,WELL_NAME,COUNTY,MUN,"
                    "PERMIT_NUM,CNSTR_DATE,TOTALDPTH"
                ),
                "resultOffset": offset,
                "resultRecordCount": _PAGE_SIZE,
                "outSR": "4326",
                "f": "json",
            })
            url = f"{_SERVICE}?{params}"
            with urllib.request.urlopen(url, timeout=60) as r:
                data = json.loads(r.read())

            features = data.get("features", [])
            if not features:
                break

            for feat in features:
                attrs = feat.get("attributes", {})
                geom = feat.get("geometry", {})
                # Embed geometry coords into attributes for normalize_row
                if geom:
                    attrs["_lon"] = geom.get("x")
                    attrs["_lat"] = geom.get("y")
                fh.write(json.dumps(attrs) + "\n")

            total_written += len(features)
            offset += len(features)

            if len(features) < _PAGE_SIZE:
                break

    print(f"  Downloaded {total_written:,} features → {out_jsonl}")


class NJAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "nj_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
        else:
            print(f"  Fetching NJ wells from NJDEP ArcGIS MapServer ...")
            _fetch_all(out)
        return out

    def parse(self, raw: Path) -> Iterator[dict]:
        with open(raw, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

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

        obj_id = str(row.get("OBJECTID") or "").strip()
        permit = str(row.get("PERMIT_NUM") or "").strip()
        well_id_part = permit if permit else f"obj{obj_id}"

        depth_ft = _parse_depth(str(row.get("TOTALDPTH") or ""))
        spud_date = _parse_year(str(row.get("CNSTR_DATE") or ""))

        operator = str(row.get("COMPANY_NAME") or "Unknown").strip() or "Unknown"
        county = str(row.get("COUNTY") or "Unknown").strip().title() or "Unknown"

        return {
            "id": f"nj-{well_id_part}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": "Plugged & Abandoned",
            "county": county,
            "state": "NJ",
            "source": "nj-dep",
            "well_type": "other",
        }


adapter = NJAdapter(_config)
