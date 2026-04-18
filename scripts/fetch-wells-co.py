"""
Downloads Colorado ECMC (Energy and Carbon Management Commission) well data
and writes public/data/wells-co.json in the standard Well shape.

Source: CO ECMC GIS data download (public, no auth)
  https://ecmc.state.co.us/documents/data/downloads/gis/

The ECMC publishes a well shapefile/CSV download that includes all permitted
and completed wells statewide.

Fallback: if bulk download is unavailable, the script exits non-zero and the
app falls back to whatever is committed to public/data/wells-co.json.

Run: python3 scripts/fetch-wells-co.py
Output: public/data/wells-co.json
"""

import csv
import io
import json
import math
import sys
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

# CO ECMC bulk well data download (zipped CSV)
# Verified 2026-04 — check https://ecmc.state.co.us/documents/data/downloads/gis/ if broken
ECMC_WELL_URL = "https://ecmc.state.co.us/documents/data/downloads/gis/WELLS.ZIP"

RAW_DIR = Path("data/raw/co")
RAW_ZIP = RAW_DIR / "WELLS.ZIP"
OUT_PATH = Path("public/data/wells-co.json")

STATUS_MAP = {
    "AB": "Active",
    "AC": "Active",
    "PA": "Plugged & Abandoned",
    "SI": "Inactive",
    "TA": "Temporarily Abandoned",
    "WO": "Inactive",
    "PR": "Permitted",
}

TYPE_MAP = {
    "OW": "oil",
    "GW": "gas",
    "GX": "gas",
    "OX": "oil",
    "OGW": "oil-gas",
    "WI": "injection",
    "WD": "disposal",
    "IW": "injection",
    "CW": "other",
}


def download() -> None:
    print(f"Downloading CO ECMC well data from {ECMC_WELL_URL} ...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(ECMC_WELL_URL, timeout=120, stream=True)
    resp.raise_for_status()
    with open(RAW_ZIP, "wb") as f:
        for chunk in resp.iter_content(65536):
            f.write(chunk)
    print(f"  Saved to {RAW_ZIP} ({RAW_ZIP.stat().st_size / 1e6:.1f} MB)")


def col(row: dict, *names: str) -> str:
    for name in names:
        for key in row:
            if key.strip().upper() == name.upper():
                return (row[key] or "").strip()
    return ""


def parse_wells_from_zip() -> list:
    with zipfile.ZipFile(RAW_ZIP) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith((".csv", ".txt", ".dat", ".dbf"))]
        # Prefer .csv or .txt over .dbf
        csv_names = [n for n in names if not n.lower().endswith(".dbf")]
        data_file = (csv_names or names)[0] if names else None
        if not data_file:
            raise RuntimeError(f"No data file found in ZIP. Contents: {zf.namelist()}")
        print(f"  Parsing {data_file} ...")
        with zf.open(data_file) as f:
            raw = f.read().decode("utf-8", errors="replace")

    sample = raw[:1000]
    delimiter = "\t" if "\t" in sample else ("|" if "|" in sample else ",")
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
    headers = [h.strip().upper() for h in (reader.fieldnames or [])]
    print(f"  Columns ({len(headers)}): {', '.join(headers[:12])} ...")

    wells = []
    seen = set()
    skipped = 0

    for row in reader:
        lat_s = col(row, "SURFACE_LATITUDE", "SURF_LAT", "LAT", "LATITUDE", "LATITUDE_DD", "Y",
                    "LATITUDE_WGS84")
        lon_s = col(row, "SURFACE_LONGITUDE", "SURF_LON", "LON", "LONGITUDE", "LONGITUDE_DD", "X",
                    "LONGITUDE_WGS84")
        depth_s = col(row, "TOTAL_DEPTH", "TD_FT", "TOTAL_MEASURED_DEPTH", "COMPL_DEPTH",
                      "COMPLETION_DEPTH", "MEASURED_DEPTH_FT", "DEPTH")

        try:
            lat = float(lat_s)
            lon = float(lon_s)
            depth = float(depth_s)
        except (ValueError, TypeError):
            skipped += 1
            continue

        if not math.isfinite(lat) or not math.isfinite(lon) or not math.isfinite(depth):
            skipped += 1
            continue
        if depth <= 0:
            skipped += 1
            continue
        # CO lat/lon sanity bounds
        if not (37.0 < lat < 41.1 and -109.1 < lon < -102.0):
            skipped += 1
            continue

        api = col(row, "API_NUMBER", "API_NO", "API", "WELL_ID", "WELLID")
        well_id = f"co-{api}" if api else f"co-{len(wells)}"
        if well_id in seen:
            continue
        seen.add(well_id)

        operator = col(row, "OPERATOR_NAME", "OPERATOR", "CURR_OPERATOR", "COMPANY") or "Unknown"
        status_raw = col(row, "WELL_STATUS", "STATUS_CODE", "FACILITYSTATUSTYPEDESCRIPTION",
                         "STAT", "STATUS")
        status = STATUS_MAP.get(status_raw.upper()[:2], status_raw or "Unknown")

        type_raw = col(row, "WELL_TYPE", "TYPE_CODE", "WELLTYPE", "FACILITYTYPE")
        well_type = TYPE_MAP.get(type_raw.upper()[:3], "other") if type_raw else "oil"

        county = col(row, "COUNTY", "COUNTY_NAME", "CNTY") or "Unknown"

        spud_raw = col(row, "SPUD_DATE", "SPUD")
        spud = spud_raw[:10] if len(spud_raw) >= 10 else spud_raw

        wells.append({
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": int(depth),
            "operator": operator,
            "spud_date": spud,
            "status": status,
            "county": county,
            "state": "CO",
            "source": "co-ecmc",
            "well_type": well_type,
        })

    print(f"  Parsed {len(wells)} CO wells, skipped {skipped} invalid rows")
    return wells


def main():
    if RAW_ZIP.exists():
        print(f"Using cached ZIP at {RAW_ZIP} (delete to re-download)")
    else:
        try:
            download()
        except Exception as e:
            sys.exit(f"Download failed: {e}\nCheck {ECMC_WELL_URL}")

    try:
        wells = parse_wells_from_zip()
    except Exception as e:
        sys.exit(f"Parse failed: {e}")

    if not wells:
        print("WARNING: 0 wells parsed — check column names in CSV")
        sys.exit(1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(wells, f)

    print(f"\nWrote {len(wells)} CO wells to {OUT_PATH}")
    depths = [w["depth_ft"] for w in wells]
    print(f"Depth range: {min(depths):,} – {max(depths):,} ft")
    types = {}
    for w in wells:
        types[w["well_type"]] = types.get(w["well_type"], 0) + 1
    print(f"Well types: {types}")


if __name__ == "__main__":
    main()
