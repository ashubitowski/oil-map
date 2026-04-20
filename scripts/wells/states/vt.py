"""
Vermont — VT Agency of Natural Resources, Private Wells (Well Driller Reports)

Source: Vermont ANR Open Data — OPENDATA_ANR_WATER_SP_NOCACHE_v2, layer 162
  https://anrmaps.vermont.gov/arcgis/rest/services/Open_Data/
          OPENDATA_ANR_WATER_SP_NOCACHE_v2/MapServer/162
  ~120k wells. All well completion reports filed since 1966 — domestic,
  geothermal, monitoring, municipal, industrial, and injection wells.
  Vermont has no commercial oil/gas production; the handful of historical
  hydrocarbon exploration wells (1957–1984) are not in this database.

Fields used:
  OBJECTID        — unique row identifier
  LATDD / LONGDD  — WGS84 decimal degrees (populated in the attributes)
  WellDepth       — total depth, feet
  WellType        — "Bedrock", "Gravel", "Monitoring", "Other", ""
  WellUseCode     — intended use (Domestic, Geothermal, Monitoring Well …)
  DrillerName     — company / driller name
  Town            — Vermont town (used as county proxy)
  DateCompleted   — epoch milliseconds
  WellReasonCode  — "New Supply", "Geothermal", "Replacement", …
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

_BASE_URL = (
    "https://anrmaps.vermont.gov/arcgis/rest/services"
    "/Open_Data/OPENDATA_ANR_WATER_SP_NOCACHE_v2/MapServer/162"
)

_PAGE_SIZE = 2000

_config = BaseConfig(
    state="VT",
    source_label="vt-vgs",
    url=_BASE_URL,
    bounds=(42.7, 45.0, -73.4, -71.5),
    output=Path("public/data/wells-vt.json"),
    raw_dir=Path("data/raw/vt"),
    require_depth=False,
    status_map={
        # Vermont well driller reports don't carry a production status; derive
        # from WellUseCode where meaningful.
        "ABANDONED":    "Plugged & Abandoned",
        "TEST":         "Inactive",
    },
    well_type_map={
        # WellType field
        "BEDROCK":      "other",
        "GRAVEL":       "other",
        "MONITORING":   "other",
        "OTHER":        "other",
        # WellUseCode overrides (applied in normalize_row)
        "GEOTHERMAL":   "other",
        "INJECTION":    "injection",
        "MONITORING WELL": "other",
        "RECHARGE":     "injection",
        "TEST":         "other",
    },
)


def _fetch_all(out_jsonl: Path) -> int:
    """Paginate the MapServer layer using resultOffset; append JSONL. Returns count."""
    url = _BASE_URL + "/query"
    params = {
        "where": "1=1",
        "outFields": (
            "OBJECTID,LATDD,LONGDD,WellDepth,WellType,"
            "WellUseCode,DrillerName,Town,DateCompleted,WellReasonCode"
        ),
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
        "resultRecordCount": _PAGE_SIZE,
    }
    offset = 0
    total = 0

    with open(out_jsonl, "w", encoding="utf-8") as fh:
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
                # Prefer geometry coords; LATDD/LONGDD are also populated but
                # geometry is the authoritative spatial reference.
                attrs["_lat"] = geom.get("y") or attrs.get("LATDD")
                attrs["_lon"] = geom.get("x") or attrs.get("LONGDD")
                fh.write(json.dumps(attrs) + "\n")

            total += len(features)
            if total % 20000 == 0:
                print(f"    ... {total:,} features fetched")

            # Stop when the server signals no more pages
            if not data.get("exceededTransferLimit", False) and len(features) < _PAGE_SIZE:
                break
            offset += len(features)

    return total


class VTAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "vt_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Fetching {_BASE_URL} (paginating, {_PAGE_SIZE}/page) ...")
        total = _fetch_all(out)
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
            lat = float(row.get("_lat") or 0)
            lon = float(row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        obj_id = str(row.get("OBJECTID") or "").strip()

        # Depth — feet, float in source
        depth_raw = row.get("WellDepth")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw is not None else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 35000:
            depth_ft = 0

        # Spud / completion date — epoch ms
        date_ms = row.get("DateCompleted")
        spud_date = ""
        if date_ms:
            try:
                ms = int(date_ms)
                if ms > 0:
                    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
                    if 1850 <= dt.year <= 2040:
                        spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        # Status — derive from WellUseCode
        use_code = str(row.get("WellUseCode") or "").strip().upper()
        status = cfg.resolve_status(use_code)
        if not status or status == "Unknown":
            status = "Unknown"

        # Well type — WellUseCode takes priority over WellType for specificity
        well_type_raw = use_code if use_code else str(row.get("WellType") or "").strip().upper()
        well_type = cfg.well_type_map.get(well_type_raw, "other")

        # Operator / driller
        operator = str(row.get("DrillerName") or "Unknown").strip() or "Unknown"

        # County — Vermont uses towns, not counties; Town is the finest admin unit
        town = str(row.get("Town") or "Unknown").strip() or "Unknown"

        well_id = f"vt-{obj_id}" if obj_id else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": town,
            "state": "VT",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = VTAdapter(_config)
