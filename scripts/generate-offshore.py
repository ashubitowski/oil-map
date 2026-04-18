"""
Downloads BOEM OCS borehole (well) data for the Gulf of Mexico region and
writes public/data/wells-offshore.json in the same shape as wells.json,
with extra fields: water_depth_ft and source="boem".

Canonical source: BOEM Borehole bulk download
  https://www.data.boem.gov/Main/Files/Borehole.zip
  (public, no auth required)

The ZIP contains a pipe-delimited text file with all OCS boreholes.
GOM wells are filtered by REGION_CODE = 'G'.

Run: python3 scripts/generate-offshore.py [--region GOM]
Regions: GOM (Gulf of Mexico, default) — Pacific/Alaska stubbed.
"""

import csv
import io
import json
import math
import argparse
import sys
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

BOEM_ZIP_URL = "https://www.data.boem.gov/Main/Files/Borehole.zip"
RAW_DIR = Path("data/raw/boem")
RAW_ZIP = RAW_DIR / "Borehole.zip"
OUT_PATH = Path("public/data/wells-offshore.json")

REGION_FILTER = {
    "GOM": "G",   # Gulf of Mexico
    "PAC": "P",   # Pacific
    "AK": "A",    # Alaska
}


def download_zip() -> None:
    print(f"Downloading BOEM borehole data from {BOEM_ZIP_URL} ...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(BOEM_ZIP_URL, timeout=120, stream=True)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(RAW_ZIP, "wb") as f:
        for chunk in resp.iter_content(65536):
            f.write(chunk)
            downloaded += len(chunk)
    print(f"  Downloaded {downloaded / 1e6:.1f} MB → {RAW_ZIP}")


def parse_spud_date(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    # Common formats: YYYYMMDD, YYYY-MM-DD, MM/DD/YYYY
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    if len(raw) == 10 and raw[4] == "-":
        return raw
    if "/" in raw:
        parts = raw.split("/")
        if len(parts) == 3:
            m, d, y = parts
            return f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
    return raw


def load_wells_from_zip(region_filter: str) -> list:
    with zipfile.ZipFile(RAW_ZIP) as zf:
        # Find the CSV/text file inside the ZIP
        names = [n for n in zf.namelist() if n.lower().endswith((".txt", ".csv", ".dat"))]
        if not names:
            raise RuntimeError(f"No text/CSV found in ZIP. Contents: {zf.namelist()}")
        data_file = names[0]
        print(f"  Parsing {data_file} (region filter: {region_filter!r}) ...")
        with zf.open(data_file) as f:
            text = f.read().decode("utf-8", errors="replace")

    # Try pipe delimiter first, then comma
    sample = text[:2000]
    delimiter = "|" if "|" in sample else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = [h.strip().upper() for h in (reader.fieldnames or [])]
    print(f"  Columns ({len(headers)}): {', '.join(headers[:15])} ...")

    def col(row: dict, *names: str) -> str:
        for name in names:
            for key in row:
                if key.strip().upper() == name:
                    return row[key].strip()
        return ""

    wells = []
    seen = set()
    skipped = 0

    for row in reader:
        region = col(row, "REGION_CODE", "REGION", "REG_CODE")
        if region_filter and region.upper() != region_filter.upper():
            continue

        lat_s = col(row, "SURFACE_LATITUDE", "SURF_LAT", "BH_LAT", "LATITUDE", "LAT")
        lon_s = col(row, "SURFACE_LONGITUDE", "SURF_LON", "BH_LON", "LONGITUDE", "LON")
        depth_s = col(row, "TOTAL_DEPTH", "TOTAL_MD_FT", "TOTAL_MEASURED_DEPTH", "TVD_FT", "DEPTH_FT")

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
        # Sanity-check GOM coordinate bounds
        if region_filter == "G" and not (-98 < lon < -80 and 23 < lat < 31):
            skipped += 1
            continue

        api = col(row, "API_WELL_NUMBER", "API_NUMBER", "API", "BOREHOLE_ID", "WELL_NUMBER")
        well_id = api or f"boem-gom-{len(wells)}"
        if well_id in seen:
            continue
        seen.add(well_id)

        operator = col(row, "COMPANY_NAME", "COMP_NAME", "OPERATOR", "OPERATOR_NAME") or "Unknown"
        status = col(row, "WELL_STATUS", "BH_STAT", "STATUS") or "Unknown"
        water_s = col(row, "WATER_DEPTH", "WATER_DEPTH_FT", "WATERDEPTH")
        lease = col(row, "LEASE_NUMBER", "LEASE_NO", "LEASE")
        area = col(row, "AREA_CODE", "AREA")
        block = col(row, "BLOCK_NUMBER", "BLOCK_NUM", "BLOCK")
        county = f"{area} {block}".strip() if (area or block) else (lease or "OCS")
        spud = parse_spud_date(col(row, "SPUD_DATE", "SPUD"))

        well: dict = {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": int(depth),
            "operator": operator,
            "spud_date": spud,
            "status": status,
            "county": county,
            "state": "GOM",
            "source": "boem",
        }
        try:
            wd = float(water_s)
            if math.isfinite(wd) and wd > 0:
                well["water_depth_ft"] = int(wd)
        except (ValueError, TypeError):
            pass

        wells.append(well)

    print(f"  Parsed {len(wells)} wells, skipped {skipped} invalid rows")
    return wells


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="GOM", choices=["GOM", "PAC", "AK"])
    args = parser.parse_args()

    if args.region != "GOM":
        print(f"Region {args.region} is stubbed — only GOM is fully implemented.")
        return

    region_filter = REGION_FILTER[args.region]

    # Download only if not already cached
    if RAW_ZIP.exists():
        print(f"Using cached ZIP at {RAW_ZIP} (delete to re-download)")
    else:
        download_zip()

    wells = load_wells_from_zip(region_filter)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(wells, f)

    print(f"\nWrote {len(wells)} offshore wells to {OUT_PATH}")
    if wells:
        depths = [w["depth_ft"] for w in wells]
        print(f"Depth range: {min(depths):,} – {max(depths):,} ft")
        water_depths = [w.get("water_depth_ft") for w in wells if "water_depth_ft" in w]
        if water_depths:
            print(f"Water depth range: {min(water_depths):,} – {max(water_depths):,} ft")


if __name__ == "__main__":
    main()
