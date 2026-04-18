"""
Colorado — CO ECMC Well Spots (location + operator) joined with completion
table (depth + spud date).

Source: CO Energy and Carbon Management Commission
  Well Spots ZIP: https://ecmc.state.co.us/documents/data/downloads/gis/WELLS.ZIP
  Completions CSV: https://ecmc.state.co.us/documents/data/downloads/gis/WELLLOGS.ZIP
    (alternate: https://ecmc.state.co.us/cogcc/facility_production.html)

The Well Spots file has lat/lon, operator, county, status, and well type but
NO depth or spud date. The completion table adds those, keyed on API number.
Wells with no matching completion record are dropped (depth unknown = useless dot).
"""

import csv
import io
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

from scripts.wells.adapters.direct_download import DirectDownloadAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import col, parse_spud_date, normalize_api, is_in_bounds

# Well Spots: lat/lon + metadata
WELLS_URL = "https://ecmc.state.co.us/documents/data/downloads/gis/WELLS.ZIP"
# Well Logs/Completions: API → total depth + spud date
LOGS_URL = "https://ecmc.state.co.us/documents/data/downloads/gis/WELLLOGS.ZIP"

_config = BaseConfig(
    state="CO",
    source_label="co-ecmc",
    url=WELLS_URL,
    bounds=(37.0, 41.1, -109.1, -102.0),
    output=Path("public/data/wells-co.json"),
    raw_dir=Path("data/raw/co"),
    status_map={
        "AB": "Active", "AC": "Active", "PA": "Plugged & Abandoned",
        "SI": "Inactive", "TA": "Temporarily Abandoned", "WO": "Inactive", "PR": "Permitted",
    },
    well_type_map={
        "OW": "oil", "GW": "gas", "GX": "gas", "OX": "oil",
        "OGW": "oil-gas", "WI": "injection", "WD": "disposal", "IW": "injection", "CW": "other",
    },
    field_map={
        "lat": ["SURFACE_LATITUDE", "SURF_LAT", "LAT", "LATITUDE", "LATITUDE_WGS84",
                "LATITUDE_DD", "Y"],
        "lon": ["SURFACE_LONGITUDE", "SURF_LON", "LON", "LONGITUDE", "LONGITUDE_WGS84",
                "LONGITUDE_DD", "X"],
        "depth_ft": ["TOTAL_DEPTH", "TD_FT", "TOTAL_MEASURED_DEPTH", "COMPL_DEPTH",
                     "COMPLETION_DEPTH", "MEASURED_DEPTH_FT", "DEPTH", "MD"],
        "api": ["API_NUMBER", "API_NO", "API", "WELL_ID", "WELLID"],
        "operator": ["OPERATOR_NAME", "OPERATOR", "CURR_OPERATOR", "COMPANY"],
        "status": ["WELL_STATUS", "STATUS_CODE", "FACILITYSTATUSTYPEDESCRIPTION", "STAT", "STATUS"],
        "well_type": ["WELL_TYPE", "TYPE_CODE", "WELLTYPE", "FACILITYTYPE"],
        "county": ["COUNTY", "COUNTY_NAME", "CNTY"],
        "spud_date": ["SPUD_DATE", "SPUD"],
    },
)


def _download_file(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  Using cached {dest}")
        return
    print(f"  Downloading {url} ...")
    resp = requests.get(url, timeout=180, stream=True)
    resp.raise_for_status()
    total = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(65536):
            f.write(chunk)
            total += len(chunk)
    print(f"  Saved {total / 1e6:.1f} MB → {dest}")


def _extract_csv(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith((".csv", ".txt", ".dat"))]
        dbfs = [n for n in zf.namelist() if n.lower().endswith(".dbf")]
        chosen = (names or dbfs)[0] if (names or dbfs) else None
        if not chosen:
            raise RuntimeError(f"No data file in {zip_path}. Contents: {zf.namelist()}")
        with zf.open(chosen) as f:
            return f.read().decode("utf-8", errors="replace")


def _build_depth_index(logs_zip: Path) -> Dict[str, Tuple[float, str]]:
    """Return {api_10digit: (depth_ft, spud_date)} from the completion/log table."""
    text = _extract_csv(logs_zip)
    sample = text[:2000]
    delimiter = "\t" if "\t" in sample else ("|" if "|" in sample else ",")
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    index: Dict[str, Tuple[float, str]] = {}
    for row in reader:
        api_raw = col(row, "API_NUMBER", "API_NO", "API", "WELLAPINO")
        depth_s = col(row, "TOTAL_DEPTH", "TD_FT", "COMPL_DEPTH", "MEASURED_DEPTH_FT",
                      "BASE_INTERVAL_DEPTH", "PERF_BOTTOM", "DEPTH")
        spud_raw = col(row, "SPUD_DATE", "SPUD", "SPUDDATE")
        api = normalize_api(api_raw)
        if not api:
            continue
        try:
            depth = float(depth_s)
        except (ValueError, TypeError):
            continue
        if depth <= 0:
            continue
        existing = index.get(api)
        # Keep the deepest completion for this API
        if existing is None or depth > existing[0]:
            index[api] = (depth, parse_spud_date(spud_raw))
    print(f"  Completion index: {len(index):,} records")
    return index


class COAdapter(DirectDownloadAdapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        wells_zip = cfg.raw_dir / "WELLS.ZIP"
        logs_zip = cfg.raw_dir / "WELLLOGS.ZIP"
        _download_file(WELLS_URL, wells_zip)
        _download_file(LOGS_URL, logs_zip)
        # Store logs path for use in parse()
        self._logs_zip = logs_zip
        return wells_zip

    def parse(self, raw: Path) -> Iterator[dict]:
        # Build depth/spud index from completion table
        self._depth_index = _build_depth_index(self._logs_zip)
        yield from super().parse(raw)

    def normalize_row(self, row: dict) -> "Optional[dict]":
        well = super().normalize_row(row)
        if well is None:
            return None

        cfg = self.config
        api = normalize_api(col(row, "API_NUMBER", "API_NO", "API", "WELL_ID", "WELLID"))

        # Try to get depth from completion index; also from shapefile as fallback
        if api and api in self._depth_index:
            depth, spud = self._depth_index[api]
            well["depth_ft"] = int(depth)
            if spud:
                well["spud_date"] = spud
        elif well["depth_ft"] <= 0:
            # No depth from either source — drop the well
            return None

        if not is_in_bounds(well["lat"], well["lon"], cfg.bounds):
            return None
        return well


adapter = COAdapter(_config)
