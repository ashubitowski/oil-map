"""
New Hampshire — NH DES Water Well Inventory (ArcGIS FeatureServer)

Source: NH Department of Environmental Services / NH Geological Survey
  https://gis.des.nh.gov/server/rest/services/Core_GIS_Datasets/DES_Data_Secure/FeatureServer/6
  ~111k well records reported by licensed well drillers to the NH Geological Survey since
  1984 (year reporting became mandatory). The database includes bedrock, overburden/gravel,
  and other borehole types — NH has no oil/gas production history, but these deep drilled
  boreholes (many 200–600+ ft) represent the full subsurface record for the state.

Fields used:
  OBJECTID, WELL_, TOWN, DCOMP (epoch-ms), USE_, TYPE, TOTD (total depth ft),
  LATITUDE, LONGITUDE (WGS84 decimal degrees stored as attributes)

All wells are classified as well_type="other" (water supply / domestic borehole).
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
from scripts.wells.schema import is_in_bounds

_SVC_URL = (
    "https://gis.des.nh.gov/server/rest/services"
    "/Core_GIS_Datasets/DES_Data_Secure/FeatureServer/6"
)
_PAGE_SIZE = 2000

_config = BaseConfig(
    state="NH",
    source_label="nh-granit",
    category="water-other",
    url=_SVC_URL,
    bounds=(42.7, 45.3, -72.6, -70.6),
    output=Path("public/data/wells-nh.json"),
    raw_dir=Path("data/raw/nh"),
    require_depth=False,
    status_map={},      # no status field; all are completed water wells
    well_type_map={
        "BEDROCK (DRILLED)":  "other",
        "OVERBURDEN":         "other",
        "GRAVEL":             "other",
        "GRAVEL PACKED":      "other",
        "DUG":                "other",
        "DRIVEN":             "other",
        "SPRING":             "other",
    },
)


class NHAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        out = cfg.raw_dir / "nh_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        url = _SVC_URL + "/query"
        params = {
            "where": "1=1",
            "outFields": (
                "OBJECTID,WELL_,TOWN,DCOMP,USE_,TYPE,TOTD,LATITUDE,LONGITUDE"
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
                    # LATITUDE/LONGITUDE are stored as attribute fields (WGS84 decimal degrees)
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

        # Total depth (feet); string field, may be None or empty
        depth_raw = row.get("TOTD")
        try:
            depth_ft = int(float(str(depth_raw).strip())) if depth_raw is not None else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 35000:
            depth_ft = 0

        # Completion date: epoch-ms integer from ArcGIS
        dcomp_raw = row.get("DCOMP")
        spud_date = ""
        if dcomp_raw:
            try:
                dt = datetime.fromtimestamp(int(dcomp_raw) / 1000, tz=timezone.utc)
                spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        # Well type
        well_type_raw = str(row.get("TYPE") or "").strip().upper()
        well_type = cfg.resolve_well_type(well_type_raw) if well_type_raw else "other"

        # Town used as county proxy (NH GRANIT stores town, not county)
        town = str(row.get("TOWN") or "Unknown").strip().title() or "Unknown"

        # Well ID from WELL_ field
        wellno = row.get("WELL_")
        obj_id = row.get("OBJECTID")
        id_part = str(wellno).strip() if wellno else f"obj{obj_id}"
        well_id = f"nh-{id_part}"

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": "Unknown",   # driller not exported in public fields
            "spud_date": spud_date,
            "status": "Unknown",
            "county": town,          # town-level; no county field in source
            "state": "NH",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = NHAdapter(_config)
