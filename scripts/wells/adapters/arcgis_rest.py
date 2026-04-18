"""
Pattern B: ArcGIS REST FeatureServer — paginated GeoJSON.

Usage:
  ArcGISAdapter(config).run()

Config requirements:
  config.url = FeatureServer layer URL ending in /0, /1, etc.
               e.g. "https://services.arcgis.com/.../FeatureServer/0"
  config.field_map: all fields come from the attributes dict; geometry
                    supplies lat/lon automatically (no "lat"/"lon" keys needed
                    unless the source stores coords as attributes).
"""

import sys
import json
from pathlib import Path
from typing import Iterator, Optional

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

from scripts.wells.adapters.base import Adapter
from scripts.wells.schema import col

RECORD_COUNT = 2000  # stay under ArcGIS server limits


class ArcGISAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / f"{cfg.state.lower()}_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        url = cfg.url.rstrip("/") + "/query"
        params = {
            "where": "1=1",
            "outFields": "*",
            "f": "json",
            "resultRecordCount": RECORD_COUNT,
            "outSR": "4326",
        }
        offset = 0
        total = 0
        print(f"  Fetching {cfg.url} (paginating, {RECORD_COUNT}/page) ...")
        with open(out, "w") as f:
            while True:
                params["resultOffset"] = offset
                resp = requests.get(url, params=params, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                features = data.get("features", [])
                if not features:
                    break
                for feat in features:
                    f.write(json.dumps(feat) + "\n")
                total += len(features)
                if total % 10000 == 0:
                    print(f"    ... {total:,} features fetched")
                # ArcGIS signals last page by not setting exceededTransferLimit
                if not data.get("exceededTransferLimit", False) and len(features) < RECORD_COUNT:
                    break
                offset += len(features)
        print(f"  Downloaded {total:,} features → {out}")
        return out

    def parse(self, raw: Path) -> Iterator[dict]:
        with open(raw) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                feat = json.loads(line)
                attrs = feat.get("attributes", {})
                geom = feat.get("geometry", {})
                # Flatten geometry into attrs so normalize_row can find lat/lon
                if geom:
                    if "y" in geom and "x" in geom:
                        attrs["_lat"] = geom["y"]
                        attrs["_lon"] = geom["x"]
                    elif "latitude" in geom and "longitude" in geom:
                        attrs["_lat"] = geom["latitude"]
                        attrs["_lon"] = geom["longitude"]
                yield attrs

    def normalize_row(self, row: dict) -> Optional[dict]:
        # Inject _lat/_lon into field_map so base normalize_row finds them
        cfg = self.config
        fm = dict(cfg.field_map)
        if "_lat" in row and "lat" not in fm:
            fm["lat"] = ["_lat"]
        if "_lon" in row and "lon" not in fm:
            fm["lon"] = ["_lon"]
        # Temporarily swap field_map
        original = cfg.field_map
        cfg.field_map = fm
        result = super().normalize_row(row)
        cfg.field_map = original
        return result
