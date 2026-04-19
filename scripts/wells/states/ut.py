"""
Utah — DOGM Energy Wells (Utah DNR Trust Lands ArcGIS FeatureServer)

Source: Utah Division of Oil, Gas and Mining via Trust Lands ArcGIS
  https://gis.trustlands.utah.gov/mapping/rest/services/Energy_Wells_DOGM/FeatureServer/4
  ~40k wells. Geometry returned in WGS84 with outSR=4326.

No total depth field in this layer. Date fields are Unix milliseconds.
"""

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_SERVICE = (
    "https://gis.trustlands.utah.gov/mapping/rest/services"
    "/Energy_Wells_DOGM/FeatureServer/4/query"
)
_PAGE_SIZE = 2000

_config = BaseConfig(
    state="UT",
    source_label="ut-dogm",
    url=_SERVICE,
    bounds=(36.9, 42.1, -114.1, -109.0),
    output=Path("public/data/wells-ut.json"),
    raw_dir=Path("data/raw/ut"),
    require_depth=False,
    status_map={
        "A":   "Active",
        "P":   "Active",
        "APD": "Permitted",
        "I":   "Inactive",
        "S":   "Inactive",
        "TA":  "Inactive",
        "LA":  "Plugged & Abandoned",
        "PA":  "Plugged & Abandoned",
        "RET": "Unknown",
    },
    well_type_map={
        "OW":  "oil",
        "GW":  "gas",
        "OWI": "oil",
        "CD":  "gas",
        "WI":  "injection",
        "WD":  "disposal",
        "D":   "other",
        "TW":  "other",
        "WS":  "other",
    },
)


def _ms_to_iso(ms: Optional[int]) -> str:
    if not ms:
        return ""
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.date().isoformat()
    except (OSError, OverflowError, ValueError):
        return ""


def _fetch_all(out_jsonl: Path) -> None:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    offset = 0
    total = 0
    fields = "api,wellname,operator,county,wellstatus,welltype,origcompld,eventdate"

    with open(out_jsonl, "w") as fh:
        while True:
            params = urllib.parse.urlencode({
                "where": "1=1",
                "outFields": fields,
                "outSR": "4326",
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
                geom = feat.get("geometry") or {}
                row["_lon"] = geom.get("x")
                row["_lat"] = geom.get("y")
                fh.write(json.dumps(row) + "\n")

            total += len(feats)
            offset += len(feats)

            if total % 10000 == 0 or len(feats) < _PAGE_SIZE:
                print(f"    ... {total:,} features fetched", flush=True)

            if len(feats) < _PAGE_SIZE:
                break

    print(f"  Downloaded {total:,} features → {out_jsonl}")


class UTAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "ut_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
        else:
            print(f"  Fetching UT wells from DOGM ArcGIS FeatureServer ...")
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
            lat = float(row.get("_lat") or 0)
            lon = float(row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("api") or "").strip()
        if not api_raw:
            return None

        # origcompld is the most reliable date (original completion date)
        date_ms = row.get("origcompld") or row.get("eventdate")
        spud_date = _ms_to_iso(date_ms) if isinstance(date_ms, (int, float)) else ""

        status = cfg.resolve_status((row.get("wellstatus") or "").strip().upper())
        well_type = cfg.resolve_well_type((row.get("welltype") or "").strip().upper())
        operator = str(row.get("operator") or "Unknown").strip() or "Unknown"
        county = str(row.get("county") or "Unknown").strip().title() or "Unknown"

        return {
            "id": f"ut-{normalize_api(api_raw)}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": 0,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "UT",
            "source": "ut-dogm",
            "well_type": well_type,
        }


adapter = UTAdapter(_config)
