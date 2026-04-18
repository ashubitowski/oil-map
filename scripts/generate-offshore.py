"""
Downloads BOEM OCS borehole (well) data for the Gulf of Mexico region and
writes public/data/wells-offshore.json in the same shape as wells.json,
with extra fields: water_depth_ft and source="boem".

Source: BOEM OCS Borehole data via BSEE public API
API docs: https://www.bsee.gov/tools-center/bsee-data-center
Run: python3 scripts/generate-offshore.py [--region GOM]

Regions: GOM (Gulf of Mexico, default), PAC (Pacific), AK (Alaska - stub)
"""

import json
import argparse
import math
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

# BOEM/BSEE Well Data REST endpoint (OCS Borehole)
# ESRI FeatureService — paginated JSON
BSEE_ENDPOINT = "https://services1.arcgis.com/QWC9sOHQxdWj7d2k/arcgis/rest/services/Boreholes/FeatureServer/0/query"

# Region → approximate bounding box [min_lon, min_lat, max_lon, max_lat]
REGION_BOUNDS = {
    "GOM": (-97.5, 23.5, -80.5, 30.5),   # Gulf of Mexico OCS
    "PAC": (-126.0, 32.0, -117.0, 49.5),  # Pacific OCS (stub)
    "AK":  (-180.0, 54.0, -130.0, 72.0),  # Alaska OCS (stub)
}

OUT_PATH = Path("public/data/wells-offshore.json")
RAW_DIR = Path("data/raw/boem")


def fetch_page(region_code: str, offset: int, count: int = 1000) -> list:
    bbox = REGION_BOUNDS[region_code]
    geo_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    params = {
        "geometry": geo_str,
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": (
            "API_WELL_NUMBER,WELL_NAME,SPUD_DATE,COMPLETION_DATE,"
            "BH_STAT,TOTAL_MD_FT,WATER_DEPTH,BH_LAT,BH_LON,"
            "COMP_NAME,LEASE_NUMBER,AREA_CODE,BLOCK_NUM"
        ),
        "returnGeometry": "true",
        "f": "json",
        "resultOffset": offset,
        "resultRecordCount": count,
        "where": "TOTAL_MD_FT IS NOT NULL AND BH_LAT IS NOT NULL",
    }
    resp = requests.get(BSEE_ENDPOINT, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"API error: {data['error']}")
    features = data.get("features", [])
    exceeded = data.get("exceededTransferLimit", False)
    return features, exceeded


def parse_spud_date(raw) -> str:
    """Convert epoch millis or YYYYMMDD string to YYYY-MM-DD."""
    if raw is None:
        return ""
    if isinstance(raw, (int, float)) and raw > 1e9:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(raw / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    raw = str(raw)
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw


def features_to_wells(features: list, region_code: str) -> list:
    wells = []
    seen_ids = set()
    for feat in features:
        props = feat.get("attributes") or feat.get("properties") or {}
        geo = feat.get("geometry") or {}

        lat = props.get("BH_LAT") or (geo.get("y") if geo else None)
        lon = props.get("BH_LON") or (geo.get("x") if geo else None)
        if not lat or not lon or not math.isfinite(lat) or not math.isfinite(lon):
            continue

        depth = props.get("TOTAL_MD_FT")
        if not depth or not math.isfinite(float(depth)):
            continue

        api = str(props.get("API_WELL_NUMBER") or "")
        well_name = str(props.get("WELL_NAME") or "")
        well_id = api or well_name or f"boem-{region_code}-{len(wells)}"
        if well_id in seen_ids:
            continue
        seen_ids.add(well_id)

        lease = str(props.get("LEASE_NUMBER") or "")
        area = str(props.get("AREA_CODE") or "")
        block = str(props.get("BLOCK_NUM") or "")
        operator = str(props.get("COMP_NAME") or "Unknown")
        status = str(props.get("BH_STAT") or "Unknown")
        water_depth = props.get("WATER_DEPTH")
        spud_date = parse_spud_date(props.get("SPUD_DATE"))

        county = f"{area} {block}".strip() if area else lease or "OCS"

        well = {
            "id": well_id,
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "depth_ft": int(float(depth)),
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": region_code,
            "source": "boem",
        }
        if water_depth is not None and math.isfinite(float(water_depth)):
            well["water_depth_ft"] = int(float(water_depth))

        wells.append(well)
    return wells


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="GOM", choices=list(REGION_BOUNDS.keys()))
    args = parser.parse_args()

    if args.region != "GOM":
        print(f"Region {args.region} is stubbed — only GOM is fully implemented.")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching BOEM OCS borehole data for {args.region}...")
    all_features = []
    offset = 0
    page = 0
    while True:
        page += 1
        try:
            features, exceeded = fetch_page(args.region, offset)
        except Exception as exc:
            print(f"  Page {page} failed: {exc}")
            print("\nIf this fails, the BOEM ESRI endpoint may have changed.")
            print("Check: https://www.bsee.gov/tools-center/bsee-data-center")
            break

        all_features.extend(features)
        print(f"  Page {page}: {len(features)} features (total {len(all_features)})")
        if not features or not exceeded:
            break
        offset += len(features)

    print(f"\nParsing {len(all_features)} features...")
    wells = features_to_wells(all_features, args.region)

    # Cache raw data
    raw_path = RAW_DIR / f"boem_{args.region.lower()}_raw.json"
    with open(raw_path, "w") as f:
        json.dump(all_features, f)
    print(f"Raw data cached to {raw_path}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(wells, f, indent=2)

    print(f"\nWrote {len(wells)} offshore wells to {OUT_PATH}")
    if wells:
        depths = [w["depth_ft"] for w in wells]
        print(f"Depth range: {min(depths):,} – {max(depths):,} ft")
        water_depths = [w["water_depth_ft"] for w in wells if "water_depth_ft" in w]
        if water_depths:
            print(f"Water depth range: {min(water_depths):,} – {max(water_depths):,} ft")


if __name__ == "__main__":
    main()
