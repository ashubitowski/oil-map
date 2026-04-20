"""
Idaho — Idaho Department of Lands Oil and Gas Wells (ArcGIS FeatureServer)

Source: IDL Oil and Gas Well Data (public Esri-hosted service)
  https://services2.arcgis.com/1cvrwLhZRFh3okEF/arcgis/rest/services/IDL_Oil_and_Gas_Well_Data/FeatureServer
  Layer 19: Active Oil and Gas Wells
  Layer 18: Inactive Oil and Gas Wells

Fields used:
  lattitudeWGS84  — WGS84 latitude
  longitudeWGS84  — WGS84 longitude
  API             — API well number
  OPERATOR        — operator name
  TOTAL_DEPTH     — total depth in feet
  End_Drilling_Date — epoch ms; used as spud date proxy
  WellStatus      — detailed well status string
  Status          — broad status (Active / Inactive)
  County          — county name

Note: Idaho has a small number of wells (~500 active + ~2500 inactive).
      require_depth=False because many historic wells lack depth.
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
from scripts.wells.schema import is_in_bounds, normalize_api, parse_spud_date

_BASE_URL = (
    "https://services2.arcgis.com/1cvrwLhZRFh3okEF/arcgis/rest/services"
    "/IDL_Oil_and_Gas_Well_Data/FeatureServer"
)
# Layer 19 = Active, Layer 18 = Inactive
_LAYERS = [19, 18]
RECORD_COUNT = 2000


_config = BaseConfig(
    state="ID",
    source_label="id-idl",
    url=_BASE_URL,
    bounds=(41.9, 49.0, -117.3, -111.0),
    output=Path("public/data/wells-id.json"),
    raw_dir=Path("data/raw/id"),
    require_depth=False,
    status_map={
        # Active layer statuses
        "PRODUCING":                    "Active",
        "ACTIVE":                       "Active",
        "INJECTION":                    "Active",
        "ENHANCED RECOVERY":            "Active",
        "SHUT IN":                      "Inactive",
        "TEMPORARILY ABANDONED":        "Inactive",
        "INACTIVE":                     "Inactive",
        # Inactive layer statuses
        "DRY HOLE OR NOT DRILLED":      "Plugged & Abandoned",
        "PLUGGED AND ABANDONED":        "Plugged & Abandoned",
        "ABANDONED":                    "Plugged & Abandoned",
        "PLUGGED":                      "Plugged & Abandoned",
        "EXPIRED":                      "Unknown",
        "PERMIT EXPIRED":               "Unknown",
        "CANCELLED":                    "Unknown",
        "UNKNOWN":                      "Unknown",
    },
    well_type_map={
        "PRODUCING":            "oil",
        "ACTIVE":               "oil",
        "INJECTION":            "injection",
        "ENHANCED RECOVERY":    "injection",
        "DRY HOLE OR NOT DRILLED": "other",
        "PLUGGED AND ABANDONED":"other",
        "ABANDONED":            "other",
    },
)


class IDAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        out = cfg.raw_dir / "id_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        total = 0
        with open(out, "w") as f:
            for layer_id in _LAYERS:
                layer_url = f"{_BASE_URL}/{layer_id}/query"
                params = {
                    "where": "1=1",
                    "outFields": "*",
                    "f": "json",
                    "resultRecordCount": RECORD_COUNT,
                    "outSR": "4326",
                }
                offset = 0
                layer_count = 0
                print(f"  Fetching layer {layer_id} from {_BASE_URL}/{layer_id} ...")
                while True:
                    params["resultOffset"] = offset
                    resp = requests.get(layer_url, params=params, timeout=60)
                    resp.raise_for_status()
                    data = resp.json()
                    features = data.get("features", [])
                    if not features:
                        break
                    for feat in features:
                        attrs = feat.get("attributes", {})
                        geom = feat.get("geometry", {})
                        if geom and "x" in geom and "y" in geom:
                            attrs["_lon"] = geom["x"]
                            attrs["_lat"] = geom["y"]
                        f.write(json.dumps(attrs) + "\n")
                    layer_count += len(features)
                    if not data.get("exceededTransferLimit", False) and len(features) < RECORD_COUNT:
                        break
                    offset += len(features)
                print(f"    Layer {layer_id}: {layer_count:,} features")
                total += layer_count

        print(f"  Downloaded {total:,} total features → {out}")
        return out

    def parse(self, raw: Path) -> Iterator[dict]:
        with open(raw) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Coordinates — prefer the geometry-derived values, fall back to
        # the attribute columns (which the service also stores as WGS84)
        try:
            lat = float(row.get("_lat") or row.get("lattitudeWGS84") or 0)
            lon = float(row.get("_lon") or row.get("longitudeWGS84") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API") or "").strip()

        operator = str(row.get("OPERATOR") or "Unknown").strip() or "Unknown"

        try:
            depth_ft = int(float(row.get("TOTAL_DEPTH") or 0))
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 35000:
            depth_ft = 0

        # End_Drilling_Date is epoch milliseconds
        spud_date = ""
        end_drill = row.get("End_Drilling_Date")
        if end_drill:
            try:
                import datetime
                dt = datetime.datetime.utcfromtimestamp(int(end_drill) / 1000)
                spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                spud_date = ""

        well_status_raw = str(row.get("WellStatus") or row.get("Status") or "").strip().upper()
        status = cfg.resolve_status(well_status_raw)
        well_type = cfg.resolve_well_type(well_status_raw)

        county = str(row.get("County") or "Unknown").strip() or "Unknown"

        well_id = f"id-{normalize_api(api_raw)}" if api_raw else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "ID",
            "source": "id-idl",
            "well_type": well_type,
        }


adapter = IDAdapter(_config)
