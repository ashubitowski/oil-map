"""
West Virginia — WVDEP Oil & Gas Wells (TAGIS ArcGIS MapServer)

Source: WV Department of Environmental Protection, TAGIS enterprise
  https://tagis.dep.wv.gov/arcgis/rest/services/WVDEP_enterprise/oil_gas/MapServer/7
  ~153k wells. Requires SSL verification bypass (self-signed cert on TAGIS).
  No numeric depth field (depth stored as categorical text). Geometry in WGS84.
"""

import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds, parse_spud_date

_SERVICE = (
    "https://tagis.dep.wv.gov/arcgis/rest/services"
    "/WVDEP_enterprise/oil_gas/MapServer/7/query"
)
_PAGE_SIZE = 3000

_WV_COUNTY = {
    "001": "Barbour", "003": "Berkeley", "005": "Boone", "007": "Braxton",
    "009": "Brooke", "011": "Cabell", "013": "Calhoun", "015": "Clay",
    "017": "Doddridge", "019": "Fayette", "021": "Gilmer", "023": "Grant",
    "025": "Greenbrier", "027": "Hampshire", "029": "Hancock", "031": "Hardy",
    "033": "Harrison", "035": "Jackson", "037": "Jefferson", "039": "Kanawha",
    "041": "Lewis", "043": "Lincoln", "045": "Logan", "047": "Marion",
    "049": "Marshall", "051": "Mason", "053": "Mcdowell", "055": "Mercer",
    "057": "Mineral", "059": "Mingo", "061": "Monongalia", "063": "Monroe",
    "065": "Morgan", "067": "Nicholas", "069": "Ohio", "071": "Pendleton",
    "073": "Pleasants", "075": "Pocahontas", "077": "Preston", "079": "Putnam",
    "081": "Raleigh", "083": "Randolph", "085": "Ritchie", "087": "Roane",
    "089": "Summers", "091": "Taylor", "093": "Tucker", "095": "Tyler",
    "097": "Upshur", "099": "Wayne", "101": "Webster", "103": "Wetzel",
    "105": "Wirt", "107": "Wood", "109": "Wyoming",
}

_config = BaseConfig(
    state="WV",
    source_label="wv-dep",
    url=_SERVICE,
    bounds=(37.2, 40.6, -82.6, -77.7),
    output=Path("public/data/wells-wv.json"),
    raw_dir=Path("data/raw/wv"),
    require_depth=False,
    status_map={
        "ACTIVE WELL":   "Active",
        "ABANDONED WELL":"Plugged & Abandoned",
        "PLUGGED":       "Plugged & Abandoned",
        "NEVER DRILLED": "Unknown",
    },
    well_type_map={
        "GAS PRODUCTION": "gas",
        "OIL PRODUCTION": "oil",
        "HOUSE GAS ":     "gas",
        "NOT AVAILABLE":  "other",
        "UNKNOWN":        "other",
    },
)


def _make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_all(out_jsonl: Path) -> None:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    ctx = _make_ssl_ctx()
    offset = 0
    total = 0
    fields = "api,welluse,wellstatus,county,respparty,issuedate,welldepth"

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
            with urllib.request.urlopen(f"{_SERVICE}?{params}", timeout=60, context=ctx) as r:
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

            if total % 15000 == 0 or len(feats) < _PAGE_SIZE:
                print(f"    ... {total:,} features fetched", flush=True)

            if len(feats) < _PAGE_SIZE:
                break

    print(f"  Downloaded {total:,} features → {out_jsonl}")


class WVAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "wv_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
        else:
            print(f"  Fetching WV wells from TAGIS ArcGIS MapServer ...")
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

        # County stored as 3-digit FIPS padded with leading zeros
        county_code = str(row.get("county") or "").strip().zfill(3)
        county = _WV_COUNTY.get(county_code, "Unknown")

        # issuedate format: "YYYY/MM/DD" or None
        issue_raw = str(row.get("issuedate") or "").strip()
        spud_date = parse_spud_date(issue_raw.replace("/", "-")) if issue_raw else ""

        status = cfg.resolve_status((row.get("wellstatus") or "").strip().upper())
        well_type = cfg.resolve_well_type((row.get("welluse") or "").strip().upper())
        operator = str(row.get("respparty") or "Unknown").strip() or "Unknown"

        return {
            "id": f"wv-{normalize_api(api_raw)}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": 0,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "WV",
            "source": "wv-dep",
            "well_type": well_type,
        }


adapter = WVAdapter(_config)
