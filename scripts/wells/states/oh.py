"""
Ohio — ODNR Oil & Gas Wells (ArcGIS MapServer)

Source: Ohio Department of Natural Resources, Division of Oil & Gas Resources Mgmt
  https://gis2.ohiodnr.gov/arcgis/rest/services/DOG_Services/Oilgas_Wells_10_JS_TEST/MapServer/0
  ~238k wells. Geometry in WGS84. No depth or spud date in this layer.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_SERVICE = (
    "https://gis2.ohiodnr.gov/arcgis/rest/services"
    "/DOG_Services/Oilgas_Wells_10_JS_TEST/MapServer/0/query"
)
_PAGE_SIZE = 1000

_config = BaseConfig(
    state="OH",
    source_label="oh-odnr",
    url=_SERVICE,
    bounds=(38.4, 42.0, -84.8, -80.5),
    output=Path("public/data/wells-oh.json"),
    raw_dir=Path("data/raw/oh"),
    require_depth=False,
    status_map={
        "PRODUCING":                        "Active",
        "DRILLING":                         "Active",
        "WELL DRILLED":                     "Active",
        "HISTORICAL PRODUCTION WELL":       "Active",
        "STORAGE WELL":                     "Active",
        "PLUGGED BACK":                     "Inactive",
        "FINAL RESTORATION":                "Inactive",
        "FIELD INSPECTED, WELL NOT FOUND":  "Unknown",
        "ORPHAN WELL - PENDING":            "Inactive",
        "DRY AND ABANDONED":                "Plugged & Abandoned",
        "PLUGGED AND ABANDONED":            "Plugged & Abandoned",
        "DOMESTIC WELL":                    "Other",
        "NOT DRILLED":                      "Unknown",
        "CANCELLED":                        "Unknown",
        "PERMIT EXPIRED":                   "Unknown",
        "UNKNOWN STATUS":                   "Unknown",
    },
    well_type_map={
        "OIL":                          "oil",
        "OIL AND GAS":                  "oil-gas",
        "OIL WITH GAS SHOW":            "oil",
        "OIL SHOW":                     "oil",
        "GAS":                          "gas",
        "GAS AND OIL SHOW":             "oil-gas",
        "GAS WITH OIL SHOW":            "gas",
        "GAS SHOW":                     "gas",
        "GAS STORAGE":                  "other",
        "DRY HOLE":                     "other",
        "DRY HOLE WITH GAS SHOW":       "other",
        "DRY HOLE WITH OIL SHOW":       "other",
        "DRY HOLE WITH OIL AND GAS SHOW": "other",
        "PLUGGED OIL":                  "oil",
        "PLUGGED GAS":                  "gas",
        "PLUGGED OIL AND GAS":          "oil-gas",
        "PLUGGED OIL WITH GAS SHOW":    "oil",
        "PLUGGED GAS WITH OIL SHOW":    "gas",
        "PERMITTED LOCATION":           "other",
        "STRATIGRAPHY TEST":            "other",
        "LOST HOLE":                    "other",
        "EXPIRED PERMIT":               "other",
        "UNKNOWN STATUS":               "other",
    },
)


def _fetch_all(out_jsonl: Path) -> None:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    offset = 0
    total = 0
    fields = "API_WELLNO,WL_STATUS_DESC,MapSymbol_DESC,WL_CNTY,CO_NAME,WH_LAT,WH_LONG"

    with open(out_jsonl, "w") as fh:
        while True:
            params = urllib.parse.urlencode({
                "where": "1=1",
                "outFields": fields,
                "resultOffset": offset,
                "resultRecordCount": _PAGE_SIZE,
                "f": "json",
            })
            with urllib.request.urlopen(f"{_SERVICE}?{params}", timeout=60) as r:
                data = json.loads(r.read())

            feats = data.get("features", [])
            if not feats:
                break

            for feat in feats:
                row = dict(feat.get("attributes", {}))
                fh.write(json.dumps(row) + "\n")

            total += len(feats)
            offset += len(feats)

            if total % 20000 == 0 or len(feats) < _PAGE_SIZE:
                print(f"    ... {total:,} features fetched", flush=True)

            if len(feats) < _PAGE_SIZE:
                break

    print(f"  Downloaded {total:,} features → {out_jsonl}")


class OHAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "oh_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
        else:
            print(f"  Fetching OH wells from ODNR ArcGIS MapServer ...")
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
            lat = float(row.get("WH_LAT") or 0)
            lon = float(row.get("WH_LONG") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_WELLNO") or "").strip()
        if not api_raw:
            return None

        status = cfg.resolve_status((row.get("WL_STATUS_DESC") or "").strip().upper())
        well_type = cfg.resolve_well_type((row.get("MapSymbol_DESC") or "").strip().upper())
        operator = str(row.get("CO_NAME") or "Unknown").strip() or "Unknown"
        county = str(row.get("WL_CNTY") or "Unknown").strip().title() or "Unknown"

        return {
            "id": f"oh-{normalize_api(api_raw)}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": 0,
            "operator": operator,
            "spud_date": "",
            "status": status,
            "county": county,
            "state": "OH",
            "source": "oh-odnr",
            "well_type": well_type,
        }


adapter = OHAdapter(_config)
