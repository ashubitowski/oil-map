"""
Maine — Maine Geological Survey (MGS) Water Well Database

Source: Maine Geological Survey via ArcGIS Online
  https://services1.arcgis.com/RbMX0mRVOFNTdLzd/arcgis/rest/services/MGS_Wells_Database/FeatureServer/0
  ~94k wells reported by well drillers to MGS under the 1987 Water Well Information Law.

Maine has no significant oil/gas history; all wells are water/domestic boreholes.
Classified uniformly as well_type="other" (borehole / water supply).

Fields used:
  WELLNO, LATITUDE, LONGITUDE, WELL_DEPTH_FT, WELL_USE, WELL_TYPE,
  WELL_DRILLER_COMPANY, DRILL_DATE, WELL_LOCATION_TOWN, GEOTHERMAL_WELL
"""

import json
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

_SVC_URL = (
    "https://services1.arcgis.com/RbMX0mRVOFNTdLzd"
    "/arcgis/rest/services/MGS_Wells_Database/FeatureServer/0"
)
_PAGE_SIZE = 2000

_config = BaseConfig(
    state="ME",
    source_label="me-mgs",
    url=_SVC_URL,
    bounds=(43.0, 47.5, -71.1, -66.9),
    output=Path("public/data/wells-me.json"),
    raw_dir=Path("data/raw/me"),
    require_depth=False,
    status_map={},       # no status field in MGS data
    well_type_map={
        "BEDROCK":        "other",
        "OVERBURDEN":     "other",
        "GRAVEL":         "other",
        "GRAVEL PACKED":  "other",
    },
)


class MEAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        out = cfg.raw_dir / "me_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        url = _SVC_URL + "/query"
        params = {
            "where": "1=1",
            "outFields": (
                "WELLNO,LATITUDE,LONGITUDE,WELL_DEPTH_FT,WELL_USE,WELL_TYPE,"
                "WELL_DRILLER_COMPANY,DRILL_DATE,WELL_LOCATION_TOWN,GEOTHERMAL_WELL"
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
                    # LATITUDE/LONGITUDE are attribute fields (pre-projected WGS84)
                    fh.write(json.dumps(attrs) + "\n")

                total += len(features)
                if total % 10000 == 0:
                    print(f"    ... {total:,} features fetched")

                # Stop when the server signals no more pages
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

        # Coordinates live in attribute fields LATITUDE / LONGITUDE (WGS84)
        try:
            lat = float(row.get("LATITUDE") or 0)
            lon = float(row.get("LONGITUDE") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # Depth
        depth_raw = row.get("WELL_DEPTH_FT")
        try:
            depth_ft = int(float(str(depth_raw).strip())) if depth_raw is not None else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 35000:
            depth_ft = 0

        # Drill date: stored as epoch-ms integer in ArcGIS
        drill_date_raw = row.get("DRILL_DATE")
        spud_date = ""
        if drill_date_raw:
            try:
                dt = datetime.fromtimestamp(int(drill_date_raw) / 1000, tz=timezone.utc)
                spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        # Well type
        well_type_raw = str(row.get("WELL_TYPE") or "").strip().upper()
        # Geothermal wells are a known sub-category
        geothermal = str(row.get("GEOTHERMAL_WELL") or "").strip().upper()
        if geothermal in ("Y", "YES", "1"):
            well_type = "other"  # geothermal borehole
        else:
            well_type = cfg.resolve_well_type(well_type_raw)

        # Operator / driller
        operator = str(row.get("WELL_DRILLER_COMPANY") or "Unknown").strip() or "Unknown"

        # County: MGS stores town, not county — use town as "county" proxy
        county = str(row.get("WELL_LOCATION_TOWN") or "Unknown").strip() or "Unknown"

        # ID
        wellno = row.get("WELLNO")
        well_id = f"me-{wellno}" if wellno else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": "Unknown",
            "county": county,
            "state": "ME",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = MEAdapter(_config)
