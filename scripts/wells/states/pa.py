"""
Pennsylvania — PADEP Oil & Gas Well Locations (PASDA ArcGIS REST)

Source: PA Spatial Data Access, PADEP DEP MapServer layer 22
  https://mapservices.pasda.psu.edu/server/rest/services/pasda/DEP/MapServer/22
  ~224k conventional + unconventional wells. Updated frequently.

The PASDA service has no depth field. Depths for Marcellus/Utica unconventional
wells come from a FracFocus lookup table built by scripts/wells/pa_depths.py.
Run that script first; it caches to data/raw/pa/pa_depths.json.
Wells without a FracFocus match get depth_ft=0 (gray stub in 3D mode).

SPUD_DATE is stored as Unix milliseconds (can be negative/pre-1970).
"""

import json
import urllib.parse
import urllib.request
from datetime import timezone, datetime
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import is_in_bounds

_DEPTHS_PATH = Path("data/raw/pa/pa_depths.json")


def _load_depths() -> dict[str, int]:
    """Load the FracFocus permit→depth_ft lookup (built by pa_depths.py)."""
    if not _DEPTHS_PATH.exists():
        print(f"  [pa] No depth lookup found at {_DEPTHS_PATH}. Run scripts/wells/pa_depths.py first.")
        return {}
    data = json.loads(_DEPTHS_PATH.read_text())
    print(f"  [pa] Loaded {len(data):,} depth records from FracFocus cache")
    return data

_SERVICE = (
    "https://mapservices.pasda.psu.edu/server/rest/services/pasda/DEP/MapServer/22/query"
)
_PAGE_SIZE = 1000

_config = BaseConfig(
    state="PA",
    source_label="pa-dep",
    url=_SERVICE,
    bounds=(39.7, 42.3, -80.5, -74.7),
    output=Path("public/data/wells-pa.json"),
    raw_dir=Path("data/raw/pa"),
    require_depth=False,
    status_map={
        "ACTIVE":                           "Active",
        "PLUGGED OG WELL":                  "Plugged & Abandoned",
        "ABANDONED":                        "Plugged & Abandoned",
        "DEP ABANDONED LIST":               "Plugged & Abandoned",
        "DEP ORPHAN LIST":                  "Plugged & Abandoned",
        "DEP PLUGGED":                      "Plugged & Abandoned",
        "PLUGGED UNVERIFIED":               "Plugged & Abandoned",
        "UNCHARTED MINED THROUGH":          "Plugged & Abandoned",
        "REGULATORY INACTIVE STATUS":       "Inactive",
        "CANNOT BE LOCATED":                "Unknown",
        "OPERATOR REPORTED NOT DRILLED":    "Unknown",
        "PROPOSED BUT NEVER MATERIALIZED":  "Unknown",
    },
    well_type_map={
        "OIL":                  "oil",
        "GAS":                  "gas",
        "COMB. OIL&GAS":        "oil-gas",
        "COALBED METHANE":      "gas",
        "INJECTION":            "injection",
        "WASTE DISPOSAL":       "disposal",
        "STORAGE WELL":         "other",
        "DRY HOLE":             "other",
        "OBSERVATION":          "other",
        "TEST WELL":            "other",
        "UNDETERMINED":         "other",
        "MULTIPLE WELL BORE TYPE": "other",
    },
)


def _ms_to_iso(ms: Optional[int]) -> str:
    """Convert Unix milliseconds (possibly negative/pre-1970) to YYYY-MM-DD."""
    if not ms:
        return ""
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.date().isoformat()
    except (OSError, OverflowError, ValueError):
        return ""


def _fetch_all(out_jsonl: Path) -> None:
    """Paginate the ArcGIS service and write each feature as a JSON line."""
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    offset = 0
    total_written = 0
    fields = "PERMIT_NUM,WELL_TYPE,WELL_STATU,OPERATOR,COUNTY,SPUD_DATE,LATITUDE,LONGITUDE"

    with open(out_jsonl, "w") as fh:
        while True:
            params = urllib.parse.urlencode({
                "where": "1=1",
                "outFields": fields,
                "resultOffset": offset,
                "resultRecordCount": _PAGE_SIZE,
                "f": "json",
            })
            url = f"{_SERVICE}?{params}"
            with urllib.request.urlopen(url, timeout=60) as r:
                data = json.loads(r.read())

            features = data.get("features", [])
            if not features:
                break

            for feat in features:
                fh.write(json.dumps(feat["attributes"]) + "\n")

            total_written += len(features)
            offset += len(features)

            if total_written % 10000 == 0 or len(features) < _PAGE_SIZE:
                print(f"    ... {total_written:,} features fetched", flush=True)

            if len(features) < _PAGE_SIZE:
                break

    print(f"  Downloaded {total_written:,} features → {out_jsonl}")


class PAAdapter(Adapter):
    def __init__(self, config: BaseConfig) -> None:
        super().__init__(config)
        self._depths: dict[str, int] = _load_depths()

    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "pa_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
        else:
            print(f"  Fetching PA wells from PASDA ArcGIS REST ({_SERVICE}) ...")
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
            lat = float(row.get("LATITUDE") or 0)
            lon = float(row.get("LONGITUDE") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        permit = str(row.get("PERMIT_NUM") or "").strip()
        if not permit:
            return None

        spud_ms = row.get("SPUD_DATE")
        spud_date = _ms_to_iso(spud_ms) if isinstance(spud_ms, (int, float)) else ""

        status = cfg.resolve_status((row.get("WELL_STATU") or "").strip().upper())
        well_type = cfg.resolve_well_type((row.get("WELL_TYPE") or "").strip().upper())
        operator = str(row.get("OPERATOR") or "Unknown").strip() or "Unknown"
        county = str(row.get("COUNTY") or "Unknown").strip().title() or "Unknown"

        # Look up depth from FracFocus cache; permit key is "CCC-NNNNN" (no leading zeros)
        permit_key = f"{permit.split('-')[0]}-{int(permit.split('-')[1])}" if "-" in permit else permit
        depth_ft = self._depths.get(permit_key, 0)

        return {
            "id": f"pa-{permit.replace(' ', '-')}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "PA",
            "source": "pa-dep",
            "well_type": well_type,
        }


adapter = PAAdapter(_config)
