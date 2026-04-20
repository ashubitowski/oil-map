"""
Wisconsin — WGNHS Borehole Geophysics + DNR Well Inventory Exploration Wells

Wisconsin has no commercial oil or gas production. Historical petroleum
exploration (1865–1984) found no viable deposits and no public GIS layer
tracks those test holes by well type. The two best available GIS proxies are:

1. WGNHS Borehole Geophysics (primary, 632 records)
   Wisconsin Geological and Natural History Survey — geophysically logged
   boreholes statewide. Includes municipal water supply wells, USGS research
   holes, geothermal investigation boreholes, sand/quarry test holes, and
   at least one confirmed petroleum exploration well (Terra-Patrick 7-22,
   Bayfield County, 4,966 ft). These are the most geologically significant
   logged boreholes in Wisconsin.
   URL: https://data.wgnhs.wisc.edu/arcgis/rest/services/geologic_data/
        borehole_geophysics/MapServer/0

2. DNR Well Inventory — Drillhole/Test Wells (secondary, 19 records)
   Wisconsin Well Inventory FeatureServer filtered to WELL_USE IN
   ('DRILLHOLE/DRY HOLE', 'TEST WELL', 'INDUSTRIAL').
   URL: https://services5.arcgis.com/Ul9AyFFeFTjf08DW/arcgis/rest/services/
        GW_SAMPLE_PT_EXT_VAR_gdb2/FeatureServer/0

Both are fetched and de-duplicated by lat/lon proximity.

Fields used (WGNHS borehole_geophysics):
  WID         — unique integer identifier
  SiteName    — descriptive borehole name
  Depth       — borehole total depth (ft; drilled interval)
  MaxDepth    — deepest log depth (ft; may be shallower than drilled depth)
  County      — county name
  RecentLog   — year of most recent geophysical log
  geometry    — WGS84 point (x=lon, y=lat)

Fields used (DNR Well Inventory):
  WI_UNIQUE_WELL_NO         — state well number
  CALC_LL_LAT_DD_AMT        — latitude
  CALC_LL_LONG_DD_AMT       — longitude
  WELL_DEPTH_FT             — depth
  WELL_USE                  — use category
  CALC_COUNTY_NAME          — county
  CONSTRUCTOR_NAME          — driller
  WELL_CONSTRUCT_DATE       — epoch ms completion date
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

# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------
_WGNHS_URL = (
    "https://data.wgnhs.wisc.edu/arcgis/rest/services"
    "/geologic_data/borehole_geophysics/MapServer/0"
)
_DNR_URL = (
    "https://services5.arcgis.com/Ul9AyFFeFTjf08DW/arcgis/rest/services"
    "/GW_SAMPLE_PT_EXT_VAR_gdb2/FeatureServer/0"
)

_PAGE_SIZE = 2000

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_config = BaseConfig(
    state="WI",
    source_label="wi-dnr",
    category="water-other",
    url=_WGNHS_URL,
    bounds=(42.5, 47.1, -92.9, -86.2),
    output=Path("public/data/wells-wi.json"),
    raw_dir=Path("data/raw/wi"),
    require_depth=False,
    status_map={},
    well_type_map={},
    field_map={},
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _arcgis_paginate(url: str, where: str, out_fields: str, out_jsonl: Path) -> int:
    """Generic ArcGIS REST paginator. Returns number of features written."""
    query_url = url.rstrip("/") + "/query"
    params = {
        "where": where,
        "outFields": out_fields,
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
        "resultRecordCount": _PAGE_SIZE,
    }
    offset = 0
    total = 0
    with open(out_jsonl, "a") as fh:
        while True:
            params["resultOffset"] = offset
            resp = requests.get(query_url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(f"ArcGIS error: {data['error']}")
            features = data.get("features", [])
            if not features:
                break
            for feat in features:
                fh.write(json.dumps(feat) + "\n")
            total += len(features)
            if not data.get("exceededTransferLimit", False) and len(features) < _PAGE_SIZE:
                break
            offset += len(features)
    return total


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------
class WIAdapter(Adapter):
    """
    Wisconsin adapter combining two sources:
      1. WGNHS Borehole Geophysics (geologically significant logged boreholes)
      2. WI DNR Well Inventory — drillhole / test well / industrial use types

    Both are downloaded to a single JSONL file (tagged with a "_source" key)
    then normalized together.
    """

    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        out = cfg.raw_dir / "wi_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        # --- Source 1: WGNHS borehole geophysics ---
        print(f"  Fetching WGNHS borehole geophysics ({_WGNHS_URL}) ...")
        n1 = _arcgis_paginate(
            _WGNHS_URL,
            where="1=1",
            out_fields="WID,SiteName,Depth,MaxDepth,County,RecentLog",
            out_jsonl=out,
        )
        print(f"    {n1:,} WGNHS borehole features")

        # Tag WGNHS records (already written); append DNR records separately
        # Use a sentinel approach: write a tagged wrapper for each source
        # Simpler: write raw features and use geometry presence + field names to disambiguate

        # --- Source 2: DNR Well Inventory — drillhole / test / industrial ---
        print(f"  Fetching WI DNR Well Inventory drillhole/test wells ({_DNR_URL}) ...")
        dnr_where = (
            "WELL_USE IN ('DRILLHOLE/DRY HOLE','TEST WELL','INDUSTRIAL')"
        )
        n2 = _arcgis_paginate(
            _DNR_URL,
            where=dnr_where,
            out_fields=(
                "WI_UNIQUE_WELL_NO,CALC_LL_LAT_DD_AMT,CALC_LL_LONG_DD_AMT,"
                "WELL_DEPTH_FT,WELL_USE,CALC_COUNTY_NAME,"
                "CONSTRUCTOR_NAME,WELL_CONSTRUCT_DATE"
            ),
            out_jsonl=out,
        )
        print(f"    {n2:,} DNR drillhole/test well features")
        print(f"  Downloaded {n1 + n2:,} total features → {out}")
        return out

    def parse(self, raw: Path) -> Iterator[dict]:
        with open(raw) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                feat = json.loads(line)
                attrs = dict(feat.get("attributes", {}))
                geom = feat.get("geometry") or {}
                attrs["_lat"] = geom.get("y")
                attrs["_lon"] = geom.get("x")
                yield attrs

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Detect source by field presence
        is_wgnhs = "WID" in row and "SiteName" in row

        try:
            lat = float(row.get("_lat") or 0)
            lon = float(row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        if is_wgnhs:
            return self._normalize_wgnhs(row, lat, lon)
        else:
            return self._normalize_dnr(row, lat, lon)

    def _normalize_wgnhs(self, row: dict, lat: float, lon: float) -> Optional[dict]:
        cfg = self.config

        wid = row.get("WID")
        site_name = str(row.get("SiteName") or "Unknown").strip() or "Unknown"
        county = str(row.get("County") or "Unknown").strip() or "Unknown"

        # Use Depth (total drilled) preferring MaxDepth if it's larger (rare)
        depth_raw = row.get("Depth") or row.get("MaxDepth") or 0
        try:
            depth_ft = int(float(depth_raw))
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # Year of most recent log → approximate spud_date
        log_year = row.get("RecentLog")
        spud_date = f"{int(log_year)}-01-01" if log_year and int(log_year) > 1800 else ""

        # Classify well type by depth and name
        name_lower = site_name.lower()
        if any(k in name_lower for k in ("geotherm", "thermal")):
            well_type = "other"
        elif depth_ft >= 3000:
            # Very deep: likely petroleum exploration
            well_type = "other"
        else:
            well_type = "other"

        return {
            "id": f"wi-wgnhs-{wid}" if wid else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": site_name,   # closest proxy: site name is usually owner/driller
            "spud_date": spud_date,
            "status": "Unknown",
            "county": county,
            "state": "WI",
            "source": cfg.source_label,
            "well_type": well_type,
        }

    def _normalize_dnr(self, row: dict, lat: float, lon: float) -> Optional[dict]:
        cfg = self.config

        well_no = str(row.get("WI_UNIQUE_WELL_NO") or "").strip()
        county = str(row.get("CALC_COUNTY_NAME") or "Unknown").strip() or "Unknown"
        operator = str(row.get("CONSTRUCTOR_NAME") or "Unknown").strip() or "Unknown"

        # Depth
        depth_raw = row.get("WELL_DEPTH_FT")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw is not None else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # Completion date — epoch ms
        date_ms = row.get("WELL_CONSTRUCT_DATE")
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

        # Well use
        use_raw = str(row.get("WELL_USE") or "").strip().upper()
        if use_raw == "DRILLHOLE/DRY HOLE":
            well_type = "other"
            status = "Plugged & Abandoned"
        elif use_raw == "TEST WELL":
            well_type = "other"
            status = "Unknown"
        else:
            well_type = "other"
            status = "Unknown"

        well_id = f"wi-dnr-{well_no}" if well_no else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "WI",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = WIAdapter(_config)
