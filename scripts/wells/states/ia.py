"""
Iowa — Iowa Geological Survey GeoSam Well Database (ArcGIS FeatureServer)

Source: Iowa Geological Survey (IGS) via University of Iowa / Iowa DNR
  https://services3.arcgis.com/kd9gaiUExYqUbnoq/arcgis/rest/services/GeoSam/FeatureServer/0
  ~870 oil/gas wells (well_type IN ('Oil Exploration', 'Gas Storage')).

Background
----------
Iowa has very limited commercial oil/gas production (primarily historical
exploration in the southern counties). The GeoSam database is the state's
authoritative geological well registry, maintained by the Iowa Geological
Survey (a bureau of the Iowa DNR). All public ArcGIS services specifically
labelled "oil and gas" for Iowa returned 404/400/ECONNREFUSED; GeoSam is
the authoritative source used by the Iowa DNR's own mapping applications.

Three original candidate URLs were checked and confirmed unreachable:
  • https://programs.iowadnr.gov/agsearch/ogwells/arcgis/rest/services/OGWells/MapServer/0 → 404
  • https://services.arcgis.com/8Pc2pR2sHnNSFwJ1/arcgis/rest/services/Iowa_Oil_Gas_Wells/FeatureServer/0 → 400
  • https://gis.iowadnr.gov/arcgis/rest/services/OilGas/OilGasWells/MapServer/0 → ECONNREFUSED

GeoSam URL discovered from the Iowa DNR GIS application configuration at:
  https://uiowa.maps.arcgis.com/sharing/rest/content/items/c3e64081a9b3445ab98a70fa8e13a360/data

Fields used
-----------
  latitude / longitude — WGS84 decimal degrees (stored as attributes)
  dpth_tot             — total well depth (ft)
  operator             — drilling operator / company name
  county               — county name
  drl_date             — drill date (epoch milliseconds)
  wnumber              — internal GeoSam well number (used as ID)
  well_type            — well use classification (filtered to oil/gas types)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

try:
    import requests
except ImportError:
    import sys
    sys.exit("requests not installed. Run: pip install requests")

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import is_in_bounds

_URL = (
    "https://services3.arcgis.com/kd9gaiUExYqUbnoq/arcgis/rest"
    "/services/GeoSam/FeatureServer/0"
)

# Only fetch oil/gas-relevant well types from the GeoSam registry
_OG_WELL_TYPES = ("Oil Exploration", "Gas Storage")

RECORD_COUNT = 2000

_STATUS_MAP: dict[str, str] = {
    # GeoSam does not carry a structured status field; all records default
    # to Unknown. Callers may enrich from the HLINK field if desired.
}

_WELL_TYPE_MAP: dict[str, str] = {
    "Oil Exploration": "oil",
    "Gas Storage":     "gas",
}

_config = BaseConfig(
    state="IA",
    source_label="ia-dnr",
    url=_URL,
    bounds=(40.3, 43.5, -96.6, -90.1),
    output=Path("public/data/wells-ia.json"),
    raw_dir=Path("data/raw/ia"),
    require_depth=False,
    status_map=_STATUS_MAP,
    well_type_map=_WELL_TYPE_MAP,
    field_map={},   # not used; IAAdapter overrides normalize_row
)


class IAAdapter(ArcGISAdapter):
    """
    Iowa adapter using the IGS GeoSam ArcGIS FeatureServer.

    Overrides download() to:
      - Filter to oil/gas well types only (Oil Exploration, Gas Storage)
      - Request only the fields we need

    Overrides normalize_row() to:
      - Use latitude/longitude attribute fields (WGS84, no projection needed)
      - Parse epoch-ms drill date
      - Map GeoSam fields to canonical well schema
    """

    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "ia_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        type_list = ", ".join(f"'{t}'" for t in _OG_WELL_TYPES)
        where = f"well_type IN ({type_list})"
        out_fields = "wnumber,latitude,longitude,dpth_tot,operator,county,drl_date,well_type"

        url = cfg.url.rstrip("/") + "/query"
        params = {
            "where": where,
            "outFields": out_fields,
            "outSR": "4326",
            "f": "json",
            "resultRecordCount": RECORD_COUNT,
        }
        offset = 0
        total = 0
        print(f"  Fetching {cfg.url}")
        print(f"  Filter: {where}")
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as fh:
            while True:
                params["resultOffset"] = offset
                resp = requests.get(url, params=params, timeout=60)
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
                if total % 1000 == 0:
                    print(f"    ... {total:,} features fetched")
                if not data.get("exceededTransferLimit", False) and len(features) < RECORD_COUNT:
                    break
                offset += len(features)
        print(f"  Downloaded {total:,} features → {out}")
        return out

    def parse(self, raw: Path) -> Iterator[dict]:
        with open(raw) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                feat = json.loads(line)
                attrs = feat.get("attributes", {})
                # GeoSam stores coords as attributes; also pull from geometry as fallback
                geom = feat.get("geometry") or {}
                if not attrs.get("latitude") and "y" in geom:
                    attrs["latitude"] = geom["y"]
                if not attrs.get("longitude") and "x" in geom:
                    attrs["longitude"] = geom["x"]
                yield attrs

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Coordinates — prefer attribute fields (already WGS84)
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
        depth_raw = row.get("dpth_tot")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 30000:
            depth_ft = 0

        # Drill date — stored as epoch milliseconds
        spud_date = ""
        drl_ms = row.get("drl_date")
        if drl_ms:
            try:
                dt = datetime.fromtimestamp(int(drl_ms) / 1000, tz=timezone.utc)
                if dt.year >= 1850:
                    spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        # Well type and status
        wt_raw = str(row.get("well_type") or "").strip()
        well_type = _WELL_TYPE_MAP.get(wt_raw, "other")
        status = "Unknown"  # GeoSam has no structured operational-status field

        # Operator
        operator = str(row.get("operator") or "Unknown").strip() or "Unknown"

        # County
        county = str(row.get("county") or "Unknown").strip() or "Unknown"

        # ID from GeoSam well number
        wnumber = row.get("wnumber")
        well_id = f"ia-{wnumber}" if wnumber else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "IA",
            "source": "ia-dnr",
            "well_type": well_type,
        }


adapter = IAAdapter(_config)
