"""
Delaware — DNREC Non-Public Wells (ArcGIS FeatureServer)

Source: Delaware Department of Natural Resources and Environmental Control (DNREC),
  Division of Water — Non-Public Wells layer via DE FirstMap / Delaware Environmental
  Navigator (DEN) database.
  https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Environmental/
          DE_DNREC_Monitoring_Network/FeatureServer/0

Delaware has no commercial oil or natural gas production and no onshore oil/gas
exploration well records in any public GIS dataset.  Exhaustive searches of:
  • DE FirstMap (enterprise.firstmap.delaware.gov) — all folders / services
  • DNREC geospatial data portal
  • Delaware Geological Survey (DGS) web services and data catalog
  • HIFLD national petroleum well dataset
  • FracTracker Alliance datasets
  • DE Open Data Portal (data.delaware.gov)
found no oil/gas exploration well GIS layer for the state.

The DGS acknowledges "exploratory drilling in the 1970s–1980s found no commercial
deposits of gas or oil, although one noncommercial gas deposit was discovered"
(Summary of the Geologic History of Delaware, dgs.udel.edu) — but those well
records are not published as a machine-readable GIS layer.

This adapter uses the DNREC Non-Public Wells FeatureServer (~173,000 records) as
the best available well-location dataset for Delaware.  Well types are:
  Domestic - Standard / Irrigation / Other
  Agricultural - Standard / Within CPCN
  Geothermal - Closed Loop / Recharge / Supply / Direct Exchange
  Monitor - Standard / Observation / Direct Push / Zone of Interest
  Remediation - Injection / Recovery
  Construction - Dewater / Soil Borings

All are classified as well_type="other" (no oil/gas production).

Fields used:
  PermitNumber          — unique permit integer (used as well ID)
  WellType              — see above categories
  WellStatus            — "Active", "Completed", "Permit Expired", "Abandoned", …
  TotalDepthActual      — total depth, feet (float; 0 when unpermitted)
  EstConstructDate      — epoch milliseconds (estimated construction date)
  WellContractor        — driller / contractor name
  Latitude / longitude  — WGS84 decimal degrees (attribute fields, populated for
                          almost all records)
  Geometry x/y          — WGS84 decimal degrees (outSR=4326; used as primary
                          coordinate source; Latitude/longitude as fallback)
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

_SERVICE = (
    "https://enterprise.firstmap.delaware.gov/arcgis/rest/services"
    "/Environmental/DE_DNREC_Monitoring_Network/FeatureServer/0"
)
_PAGE_SIZE = 2000

_STATUS_MAP = {
    "ACTIVE":           "Active",
    "COMPLETED":        "Active",
    "PERMIT EXPIRED":   "Plugged & Abandoned",
    "ABANDONED":        "Plugged & Abandoned",
    "PLUGGED":          "Plugged & Abandoned",
    "INACTIVE":         "Inactive",
    "PERMITTED":        "Permitted",
    "PENDING":          "Permitted",
}

_config = BaseConfig(
    state="DE",
    source_label="de-dnrec",
    category="water-other",
    url=_SERVICE,
    bounds=(38.4, 39.9, -75.8, -75.0),
    output=Path("public/data/wells-de.json"),
    raw_dir=Path("data/raw/de"),
    require_depth=False,
    status_map=_STATUS_MAP,
    well_type_map={},
)


def _fetch_all(out_jsonl: Path) -> int:
    """Paginate the FeatureServer and write each feature as a JSON line."""
    url = _SERVICE + "/query"
    params = {
        "where": "1=1",
        "outFields": (
            "PermitNumber,WellType,WellStatus,"
            "TotalDepthActual,EstConstructDate,"
            "WellContractor,Latitude,longitude"
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
                # Geometry is the authoritative coord; attribute Lat/lon as fallback
                attrs["_lat"] = geom.get("y") or attrs.get("Latitude")
                attrs["_lon"] = geom.get("x") or attrs.get("longitude")
                fh.write(json.dumps(attrs) + "\n")

            total += len(features)
            if total % 20000 == 0:
                print(f"    ... {total:,} features fetched")

            if not data.get("exceededTransferLimit", False) and len(features) < _PAGE_SIZE:
                break
            offset += len(features)

    return total


class DEAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        out = cfg.raw_dir / "de_features.jsonl"
        if out.exists():
            print(f"  Using cached {out} (delete to re-download)")
            return out

        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Fetching DE DNREC Non-Public Wells from FirstMap ...")
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

        # Coordinates — geometry injected as _lat/_lon
        try:
            lat = float(row.get("_lat") or 0)
            lon = float(row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # Depth
        depth_raw = row.get("TotalDepthActual")
        try:
            depth_ft = int(float(depth_raw)) if depth_raw is not None else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # Construction date — epoch milliseconds
        date_ms = row.get("EstConstructDate")
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

        # Status
        status_raw = str(row.get("WellStatus") or "").strip().upper()
        status = cfg.resolve_status(status_raw) if status_raw else "Unknown"

        # Contractor / driller
        operator = str(row.get("WellContractor") or "Unknown").strip() or "Unknown"

        # Well type — all are water/monitoring/geothermal, not oil/gas
        well_type = "other"

        # Unique ID from permit number
        permit = row.get("PermitNumber")
        well_id = f"de-{permit}" if permit is not None else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": "Unknown",
            "state": "DE",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = DEAdapter(_config)
