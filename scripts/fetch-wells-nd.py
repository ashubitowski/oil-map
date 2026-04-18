"""
Downloads North Dakota Oil and Gas Commission (NDIC) well data and writes
public/data/wells-nd.json in the standard Well shape.

Source: ND NDIC bulk well file (public, no auth)
  https://www.dmr.nd.gov/oilgas/bakkenwells.asp
  Direct file: https://www.dmr.nd.gov/oilgas/bakkenwells.asp
  The NDIC provides well data via their GIS download portal.
  We use the publicly accessible well attribute CSV from:
    https://www.dmr.nd.gov/oilgas/bakkenwells.asp

Fallback: if bulk download is unavailable, the script exits non-zero and the
app falls back to whatever is committed to public/data/wells-nd.json.

Run: python3 scripts/fetch-wells-nd.py
Output: public/data/wells-nd.json
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

# NDIC publishes a well attribute download at this URL (tab-delimited ZIP)
# URL verified 2026-04 — may change; check https://www.dmr.nd.gov/oilgas/
NDIC_WELL_URL = "https://www.dmr.nd.gov/oilgas/bakkenwells.asp"
# The actual downloadable bulk file:
NDIC_BULK_URL = "https://www.dmr.nd.gov/oilgas/xml/ND_WellData.zip"

RAW_DIR = Path("data/raw/nd")
RAW_ZIP = RAW_DIR / "ND_WellData.zip"
OUT_PATH = Path("public/data/wells-nd.json")

STATUS_MAP = {
    "A": "Active",
    "I": "Inactive",
    "P": "Plugged",
    "D": "Drilled",
    "C": "Completed",
    "PA": "Plugged & Abandoned",
    "TA": "Temporarily Abandoned",
}

TYPE_MAP = {
    "O": "oil",
    "OW": "oil",
    "G": "gas",
    "GW": "gas",
    "OG": "oil-gas",
    "WD": "disposal",
    "WI": "injection",
    "I": "injection",
    "D": "disposal",
}

COUNTY_FIPS = {
    "001": "Adams", "003": "Barnes", "005": "Benson", "007": "Billings",
    "009": "Bottineau", "011": "Bowman", "013": "Burke", "015": "Burleigh",
    "017": "Cass", "019": "Cavalier", "021": "Dickey", "023": "Divide",
    "025": "Dunn", "027": "Eddy", "029": "Emmons", "031": "Foster",
    "033": "Golden Valley", "035": "Grand Forks", "037": "Grant", "039": "Griggs",
    "041": "Hettinger", "043": "Kidder", "045": "La Moure", "047": "Logan",
    "049": "McHenry", "051": "McIntosh", "053": "McKenzie", "055": "McLean",
    "057": "Mercer", "059": "Morton", "061": "Mountrail", "063": "Nelson",
    "065": "Oliver", "067": "Pembina", "069": "Pierce", "071": "Ramsey",
    "073": "Ransom", "075": "Renville", "077": "Richland", "079": "Rolette",
    "081": "Sargent", "083": "Sheridan", "085": "Sioux", "087": "Slope",
    "089": "Stark", "091": "Steele", "093": "Stutsman", "095": "Towner",
    "097": "Traill", "099": "Walsh", "101": "Ward", "103": "Wells",
    "105": "Williams",
}


def download() -> None:
    print(f"Downloading NDIC well data from {NDIC_BULK_URL} ...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(NDIC_BULK_URL, timeout=120, stream=True)
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
        names = [n for n in zf.namelist() if n.lower().endswith((".csv", ".txt", ".dat"))]
        if not names:
            raise RuntimeError(f"No data file found in ZIP. Contents: {zf.namelist()}")
        data_file = names[0]
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
        lat_s = col(row, "SURFACE_LATITUDE", "SURF_LAT", "LAT", "LATITUDE", "LATITUDE_DD")
        lon_s = col(row, "SURFACE_LONGITUDE", "SURF_LON", "LON", "LONGITUDE", "LONGITUDE_DD")
        depth_s = col(row, "CURRENT_MEASURED_DEPTH", "TOTAL_DEPTH_FT", "TOTAL_DEPTH",
                      "MEASURED_DEPTH", "TD_FT", "DEPTH_FT", "COMPLETION_DEPTH", "DEPTH")

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
        # ND lat/lon sanity bounds
        if not (45.9 < lat < 49.1 and -104.1 < lon < -96.5):
            skipped += 1
            continue

        api = col(row, "API_WELL_NUMBER", "API_NO", "API", "WELL_FILE_NO")
        well_id = f"nd-{api}" if api else f"nd-{len(wells)}"
        if well_id in seen:
            continue
        seen.add(well_id)

        operator = col(row, "CURRENT_OPERATOR", "OPERATOR_COMPANY_NAME", "OPERATOR", "COMP_NAME") or "Unknown"
        status_raw = col(row, "WELL_STATUS_CODE", "STATUS_CODE", "STATUS", "WELL_STATUS")
        status = STATUS_MAP.get(status_raw.upper(), status_raw or "Unknown")

        type_raw = col(row, "WELL_TYPE_CODE", "TYPE_CODE", "WELL_TYPE", "TYPE")
        well_type = TYPE_MAP.get(type_raw.upper(), "other") if type_raw else "oil"

        county_fips = col(row, "COUNTY_CODE", "FIPS_COUNTY", "COUNTY_FIPS")
        county_name = col(row, "COUNTY_NAME", "COUNTY")
        county = county_name or COUNTY_FIPS.get(str(county_fips).zfill(3), "Unknown")

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
            "state": "ND",
            "source": "nd-ogic",
            "well_type": well_type,
        })

    print(f"  Parsed {len(wells)} ND wells, skipped {skipped} invalid rows")
    return wells


def main():
    if RAW_ZIP.exists():
        print(f"Using cached ZIP at {RAW_ZIP} (delete to re-download)")
    else:
        try:
            download()
        except Exception as e:
            sys.exit(f"Download failed: {e}\nCheck {NDIC_BULK_URL}")

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

    print(f"\nWrote {len(wells)} ND wells to {OUT_PATH}")
    depths = [w["depth_ft"] for w in wells]
    print(f"Depth range: {min(depths):,} – {max(depths):,} ft")
    types = {}
    for w in wells:
        types[w["well_type"]] = types.get(w["well_type"], 0) + 1
    print(f"Well types: {types}")


if __name__ == "__main__":
    main()
