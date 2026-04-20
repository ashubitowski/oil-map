"""
Massachusetts — MassDEP Well Location Viewer (ArcGIS FeatureServer)

Source: Massachusetts Department of Environmental Protection, Well Driller Program
  https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/Well_Location_Viewer_Data_4_26_23/FeatureServer/0
  ~127k wells reported by licensed well drillers to MassDEP since 1963 (mandatory
  reporting strengthened over time). Includes domestic, public water supply,
  irrigation, monitoring, and geothermal wells.

Massachusetts has no commercial oil/gas history and no onshore exploration wells.
The ten offshore Georges Bank OCS exploration wells (1976–1982) lie south/east of
the state bounding box and are captured by the OFFSHORE adapter. All wells here
are classified as well_type="other" (drilled borehole / water supply).

Fields used:
  Well_Completion_Report_ID, Latitude, Longitude, Total_Depth_of_Well,
  Well_Type, Drilling_Firm, Date_Drilled, Town
"""

import json
import sys
from pathlib import Path
from typing import Iterator, Optional

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import is_in_bounds

_SVC_URL = (
    "https://services1.arcgis.com/7iJyYTjCtKsZS1LR"
    "/arcgis/rest/services/Well_Location_Viewer_Data_4_26_23/FeatureServer/0"
)
_PAGE_SIZE = 1000

_config = BaseConfig(
    state="MA",
    source_label="ma-mgs",
    url=_SVC_URL,
    bounds=(41.2, 42.9, -73.5, -69.9),
    output=Path("public/data/wells-ma.json"),
    raw_dir=Path("data/raw/ma"),
    require_depth=False,
    status_map={},       # no status field; all are completed drilled wells
    well_type_map={
        "DOMESTIC":               "other",
        "PUBLIC WATER SUPPLY":    "other",
        "IRRIGATION":             "other",
        "MONITORING":             "other",
        "GEOTHERMAL - OPEN LOOP": "other",
        "NO DATA":                "other",
    },
)


def _parse_depth(raw) -> int:
    """Return integer depth in feet; 0 if missing or non-numeric."""
    if raw is None:
        return 0
    try:
        val = int(float(str(raw).strip().replace(",", "")))
        return val if 0 < val <= 35000 else 0
    except (TypeError, ValueError):
        return 0


def _parse_date(raw: str) -> str:
    """Convert 'M/D/YYYY' strings to 'YYYY-MM-DD', or '' if unparseable."""
    if not raw:
        return ""
    raw = raw.strip()
    parts = raw.split("/")
    if len(parts) == 3:
        try:
            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
            # Reject implausible dates (day=0, or year outside 1900–2030)
            if d < 1 or d > 31 or m < 1 or m > 12:
                return ""
            if y < 1900 or y > 2030:
                return ""
            return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            pass
    return ""


class MAAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        out = cfg.raw_dir / "ma_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        url = _SVC_URL + "/query"
        params = {
            "where": "1=1",
            "outFields": (
                "Well_Completion_Report_ID,Latitude,Longitude,"
                "Total_Depth_of_Well,Well_Type,Drilling_Firm,Date_Drilled,Town"
            ),
            "outSR": "4326",
            "f": "json",
            "resultRecordCount": _PAGE_SIZE,
        }
        offset = 0
        total = 0
        print(f"  Fetching {_SVC_URL} (paginating, {_PAGE_SIZE}/page) ...")

        with open(out, "w") as fh:
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
                    # Geometry is present but Latitude/Longitude are attribute fields
                    geom = feat.get("geometry", {})
                    if geom and "x" in geom and "y" in geom:
                        attrs.setdefault("Latitude", geom["y"])
                        attrs.setdefault("Longitude", geom["x"])
                    fh.write(json.dumps(attrs) + "\n")

                total += len(features)
                if total % 10000 == 0:
                    print(f"    ... {total:,} features fetched")

                if not data.get("exceededTransferLimit", False) and len(features) < _PAGE_SIZE:
                    break
                offset += len(features)

        print(f"  Downloaded {total:,} features → {out}")
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
            lat = float(row.get("Latitude") or 0)
            lon = float(row.get("Longitude") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        depth_ft = _parse_depth(row.get("Total_Depth_of_Well"))
        spud_date = _parse_date(str(row.get("Date_Drilled") or ""))

        well_type_raw = str(row.get("Well_Type") or "").strip().upper()
        well_type = cfg.resolve_well_type(well_type_raw) if well_type_raw else "other"

        operator = str(row.get("Drilling_Firm") or "Unknown").strip() or "Unknown"
        county = str(row.get("Town") or "Unknown").strip().title() or "Unknown"

        wcr_id = row.get("Well_Completion_Report_ID")
        well_id = f"ma-{wcr_id}" if wcr_id is not None else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": "Unknown",
            "county": county,
            "state": "MA",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = MAAdapter(_config)
