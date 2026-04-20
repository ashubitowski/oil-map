"""
Connecticut — CT DCP Well Driller Completion Reports (Socrata / data.ct.gov)

Source: Connecticut Department of Consumer Protection, via CT Open Data Portal
  https://data.ct.gov/resource/wphv-ux6v.json
  ~7,700 well completion reports submitted online since January 1, 2021.

Connecticut has NO commercial oil or natural gas production. The state has no
historical oil/gas exploration wells in any public GIS dataset — exhaustive
searches of CT ECO (cteco.uconn.edu), CT DEEP GIS Open Data, the CT geodata
portal, USGS NIBI, and FracTracker all returned nothing. FracTracker explicitly
documents "no wells" for Connecticut.

This dataset covers:
  - Water Supply Wells (3,516 records) — bedrock domestic/municipal supply
  - Geothermal Wells (2,155 records)   — closed-loop ground-source heat pump
  - Abandonment Reports (1,778)        — well decommissioning records
  - Non-Water Supply / Monitoring      — geotechnical borings, monitoring wells
  - Hydrofracturing, Deepening, Other  — well rehabilitation reports

Fields used:
  dcpreportid          — unique report ID (used as well ID)
  type_of_report       — Water Supply Well / Geothermal / Non-Water Supply Well …
  latitude / longitude — WGS84 decimal degrees (populated for ~7,695 of 7,704)
  depth_of_well        — total depth, feet (populated for ~3,558 of 7,704)
  drilling_company     — well contractor name
  date_of_boringabandonment — ISO date of report/boring
  well_city            — municipality (used as county proxy; CT has no county field)

Socrata REST API — paginates using $limit / $offset with 1000-row pages.
require_depth=False because many abandonment and repair records carry no depth.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import is_in_bounds

_BASE_URL = "https://data.ct.gov/resource/wphv-ux6v.json"
_PAGE_SIZE = 1000

_STATUS_MAP = {
    "ABANDONMENT": "Plugged & Abandoned",
    "WATER SUPPLY WELL": "Active",
    "GEOTHERMAL": "Active",
    "NON-WATER SUPPLY WELL": "Unknown",
    "HYDROFRACTURING": "Unknown",
    "DEEPENING WELL": "Unknown",
    "WELL CASING EXTENSION": "Unknown",
    "OTHER REPAIR": "Unknown",
}

_WELL_TYPE_MAP = {
    "WATER SUPPLY WELL": "other",
    "GEOTHERMAL": "other",
    "NON-WATER SUPPLY WELL": "other",
    "ABANDONMENT": "other",
    "HYDROFRACTURING": "other",
    "DEEPENING WELL": "other",
    "WELL CASING EXTENSION": "other",
    "OTHER REPAIR": "other",
}

_config = BaseConfig(
    state="CT",
    source_label="ct-deep",
    url=_BASE_URL,
    bounds=(40.9, 42.1, -73.7, -71.8),
    output=Path("public/data/wells-ct.json"),
    raw_dir=Path("data/raw/ct"),
    require_depth=False,
    status_map=_STATUS_MAP,
    well_type_map=_WELL_TYPE_MAP,
)


def _fetch_all(out_jsonl: Path) -> int:
    """Paginate the Socrata API and write each row as a JSON line."""
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    offset = 0
    total = 0

    with open(out_jsonl, "w", encoding="utf-8") as fh:
        while True:
            params = urllib.parse.urlencode({
                "$where": "latitude IS NOT NULL",
                "$limit": _PAGE_SIZE,
                "$offset": offset,
                "$order": "dcpreportid ASC",
            })
            url = f"{_BASE_URL}?{params}"
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                rows = json.loads(r.read())

            if not rows:
                break

            for row in rows:
                fh.write(json.dumps(row) + "\n")

            total += len(rows)

            if len(rows) < _PAGE_SIZE:
                break
            offset += len(rows)

    return total


class CTAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "ct_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Fetching CT well driller reports from data.ct.gov ...")
        total = _fetch_all(out)
        print(f"  Downloaded {total:,} records → {out}")
        return out

    def parse(self, raw: Path) -> Iterator[dict]:
        with open(raw, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Coordinates
        try:
            lat = float(row.get("latitude") or 0)
            lon = float(row.get("longitude") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # Depth
        depth_raw = row.get("depth_of_well")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw not in (None, "", "0") else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 35000:
            depth_ft = 0

        # Date — Socrata returns ISO strings like "2023-03-25T00:00:00.000"
        date_raw = str(row.get("date_of_boringabandonment") or "").strip()
        spud_date = date_raw[:10] if len(date_raw) >= 10 else ""
        # Reject clearly bogus years (some source records use 2222 as a sentinel)
        if spud_date:
            year = spud_date[:4]
            if not (1850 <= int(year) <= 2030):
                spud_date = ""

        # Report type → status / well_type
        report_type = str(row.get("type_of_report") or "").strip().upper()
        status = _STATUS_MAP.get(report_type, "Unknown")
        well_type = _WELL_TYPE_MAP.get(report_type, "other")

        # Operator / driller
        operator = str(row.get("drilling_company") or "Unknown").strip() or "Unknown"

        # County — not in dataset; use city as proxy
        city = str(row.get("well_city") or "Unknown").strip().title() or "Unknown"

        # Unique ID
        report_id = str(row.get("dcpreportid") or "").strip()
        well_id = f"ct-{report_id}" if report_id else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": city,
            "state": "CT",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = CTAdapter(_config)
