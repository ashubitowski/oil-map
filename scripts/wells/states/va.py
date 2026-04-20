"""
Virginia — Department of Energy, Division of Gas and Oil Wells

Source: Virginia Department of Energy ArcGIS REST FeatureServer
  https://energy.virginia.gov/gis/rest/services/DGO/DGO_wells/FeatureServer
  ~10-11k wells across multiple status layers.

Layers fetched:
  0 — Active Wells      (~8,600)
  1 — Pending Wells     (~19)
  2 — Pending Mods      (~27)
  3 — Facilities Permits (~65)
  4 — Permitted Undrilled Wells (~210)
  5 — Plugged Wells     (~1,968)

Fields used:
  geometry (x/y, outSR=4326)  — WGS84 coords (state requests State Plane by default)
  CoName                       — company / operator
  TblCnName                    — county name
  TblPsDesc                    — well status description
  TblOpDesc                    — operation/product type
  FiNo                         — well identifier (used as ID)
  FiDrComp                     — drill completion date (epoch ms)
  TotalDepth                   — total depth in feet (layer 0 only)
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
from scripts.wells.schema import normalize_api, is_in_bounds

_BASE_URL = "https://energy.virginia.gov/gis/rest/services/DGO/DGO_wells/FeatureServer"

# Layers to fetch and their canonical status label
_LAYERS = {
    0: "active",       # Active Wells
    1: "pending",      # Pending Wells
    2: "pending",      # Pending Well Modifications
    3: "permitted",    # Facilities Permits
    4: "permitted",    # Permitted Undrilled Wells
    5: "plugged",      # Plugged Wells
}

_PAGE_SIZE = 2000

_config = BaseConfig(
    state="VA",
    source_label="va-energy",
    url=_BASE_URL,
    bounds=(36.5, 39.5, -83.7, -75.2),
    output=Path("public/data/wells-va.json"),
    raw_dir=Path("data/raw/va"),
    require_depth=False,
    status_map={
        # Active / producing
        "PRODUCING":                        "Active",
        "STABILIZED/PRODUCING":             "Active",
        "PARTIAL PLUG/PRODUCING":           "Active",
        "DRILLING":                         "Active",
        # Inactive / shut-in
        "SHUT IN":                          "Inactive",
        "PARTIAL PLUG/SHUT IN":             "Inactive",
        "TEMPORARY PLUGGED":                "Inactive",
        "PLUGGING":                         "Inactive",
        "DRILLED/WAITING COMPLETION/PL":    "Inactive",
        "COMPLETED":                        "Inactive",
        # Plugged & Abandoned
        "PLUGGED/ABANDONED":                "Plugged & Abandoned",
        "RELEASED":                         "Plugged & Abandoned",  # permit released
        "WATER WELL RELEASE":               "Plugged & Abandoned",
        # Permitted / never drilled
        "ISSUED":                           "Permitted",
        "CONSTRUCTION":                     "Permitted",
        "CONSTRUCTED/NEVER DRILLED":        "Permitted",
        "CONSTRUCTED WAITING ON RIG":       "Permitted",
        # Unknown
        "FORFEITURE":                       "Unknown",
        "ORPHANED WELL":                    "Unknown",
        "OTHER":                            "Unknown",
    },
    well_type_map={
        "OIL":                          "oil",
        "GAS":                          "gas",
        "GAS/PIPELINE":                 "gas",
        "HORIZONTAL GAS":               "gas",
        "HORIZONTAL GAS W/PL":          "gas",
        "COAL BED":                     "gas",          # coalbed methane
        "COALBED/PIPELINE":             "gas",
        "HORIZONTAL COALBED":           "gas",
        "HORIZONTAL COALBED W/PL":      "gas",
        "GAS/CB DUAL COMPLETION":       "gas",
        "GAS/COALBED WITH PIPELINE":    "gas",
        "CARBON CREDIT":                "gas",
        "CARBON CREDIT W/PIPELINE":     "gas",
        "CONVERSION":                   "other",
        "CONVERSION/PIPELINE":          "other",
        "CONVERSION TO WATER WELL":     "other",
        "WASTE DISPOSAL":               "disposal",
        "UNDERGROUND STORAGE":          "injection",
        "SERVICE WELL":                 "other",
        "EXPLORATORY":                  "other",
        "GEOPHYSICAL":                  "other",
    },
)


def _fetch_layer(layer_id: int, out_jsonl: Path) -> int:
    """Paginate a single FeatureServer layer into a .jsonl file. Returns feature count."""
    url = f"{_BASE_URL}/{layer_id}/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": _PAGE_SIZE,
    }
    offset = 0
    total = 0

    with open(out_jsonl, "a") as fh:
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
                attrs["_lat"] = geom.get("y")
                attrs["_lon"] = geom.get("x")
                attrs["_layer_id"] = layer_id
                fh.write(json.dumps(attrs) + "\n")

            total += len(features)
            if not data.get("exceededTransferLimit", False) and len(features) < _PAGE_SIZE:
                break
            offset += len(features)

    return total


class VAAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "va_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        out.write_text("")  # create/truncate

        grand_total = 0
        for layer_id in _LAYERS:
            print(f"  Fetching layer {layer_id} ({_LAYERS[layer_id]}) ...")
            n = _fetch_layer(layer_id, out)
            print(f"    Layer {layer_id}: {n:,} features")
            grand_total += n

        print(f"  Downloaded {grand_total:,} total features → {out}")
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

        fi_no = str(row.get("FiNo") or "").strip()

        # Depth — present in layer 0 (Active Wells), null elsewhere
        depth_raw = row.get("TotalDepth")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # FiDrComp — drill completion date (epoch ms)
        spud_ms = row.get("FiDrComp")
        spud_date = ""
        if spud_ms:
            try:
                ms = int(spud_ms)
                if ms > 0:
                    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
                    # Sanity-check: discard timestamps before 1850 or after 2040
                    if 1850 <= dt.year <= 2040:
                        spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        # Determine layer-aware status: layer 0 uses TblPsDesc; other layers
        # have a single logical status from _LAYERS but may also have TblPsDesc.
        tlb_ps = str(row.get("TblPsDesc") or "").strip().upper()
        status = cfg.resolve_status(tlb_ps) if tlb_ps else "Unknown"

        well_type_raw = str(row.get("TblOpDesc") or "").strip().upper()
        well_type = cfg.resolve_well_type(well_type_raw)

        operator = str(row.get("CoName") or "Unknown").strip() or "Unknown"
        county = str(row.get("TblCnName") or "Unknown").strip().title() or "Unknown"

        well_id = f"va-{fi_no}" if fi_no else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "VA",
            "source": "va-energy",
            "well_type": well_type,
        }


adapter = VAAdapter(_config)
