"""
Bootstrap wells-manifest.json from existing well files without re-running generators.

Usage:
  python3 -m scripts.wells.generate_manifest

Run from the repo root. Reads *.meta.json siblings for counts.
Importing the registry is skipped to avoid needing `requests` installed.
"""

import json
from pathlib import Path

# [minLon, minLat, maxLon, maxLat] per registry state key
_BBOXES: dict = {
    "AK":      [-169.5, 54.5, -130.0,  71.5],
    "AL":      [ -88.5, 30.1,  -84.9,  35.0],
    "AR":      [ -94.6, 33.0,  -89.6,  36.5],
    "AZ":      [-114.8, 31.3, -109.0,  37.0],
    "CA":      [-124.5, 32.5, -114.1,  42.1],
    "CO":      [-109.1, 37.0, -102.0,  41.1],
    "CT":      [ -73.7, 41.0,  -71.8,  42.1],
    "DE":      [ -75.8, 38.5,  -75.0,  39.8],
    "FL":      [ -87.6, 24.4,  -80.0,  31.0],
    "GA":      [ -85.6, 30.4,  -80.8,  35.0],
    "HI":      [-160.2, 18.9, -154.8,  22.2],
    "IA":      [ -96.6, 40.4,  -90.1,  43.5],
    "ID":      [-117.2, 42.0, -111.0,  49.0],
    "IL":      [ -91.5, 36.9,  -87.5,  42.5],
    "IN":      [ -88.1, 37.8,  -84.8,  41.8],
    "KS":      [-102.1, 37.0,  -94.6,  40.1],
    "KY":      [ -89.6, 36.5,  -81.9,  39.2],
    "LA":      [ -94.1, 28.9,  -89.0,  33.1],
    "MA":      [ -73.5, 41.2,  -69.9,  42.9],
    "MD":      [ -79.5, 37.9,  -75.0,  39.7],
    "ME":      [ -71.1, 43.1,  -66.9,  47.5],
    "MI":      [ -90.5, 41.7,  -82.4,  48.3],
    "MN":      [ -97.2, 43.5,  -89.5,  49.4],
    "MO":      [ -95.8, 35.9,  -89.1,  40.6],
    "MS":      [ -91.7, 30.2,  -88.1,  35.0],
    "MT":      [-116.1, 44.4, -104.0,  49.1],
    "NC":      [ -84.3, 33.8,  -75.5,  36.6],
    "ND":      [-104.1, 45.9,  -96.5,  49.1],
    "NE":      [-104.1, 40.0,  -95.3,  43.0],
    "NH":      [ -72.6, 42.7,  -70.6,  45.3],
    "NJ":      [ -75.6, 38.9,  -73.9,  41.4],
    "NM":      [-109.1, 31.3, -103.0,  37.1],
    "NV":      [-120.0, 35.0, -114.0,  42.0],
    "NY":      [ -79.8, 40.5,  -71.9,  45.0],
    "OH":      [ -84.9, 38.4,  -80.5,  42.0],
    "OK":      [-103.0, 33.6,  -94.4,  37.1],
    "OFFSHORE": [-98.0, 23.0,  -80.0,  31.0],
    "OR":      [-124.6, 42.0, -116.5,  46.3],
    "PA":      [ -80.5, 39.7,  -74.7,  42.3],
    "RI":      [ -71.9, 41.1,  -71.1,  42.0],
    "SC":      [ -83.4, 32.0,  -78.5,  35.2],
    "SD":      [-104.1, 42.5,  -96.4,  45.9],
    "TN":      [ -90.3, 35.0,  -81.6,  36.7],
    "TX":      [-106.7, 25.8,  -93.5,  36.5],
    "UT":      [-114.1, 37.0, -109.0,  42.1],
    "VA":      [ -83.7, 36.5,  -75.2,  39.5],
    "VT":      [ -73.4, 42.7,  -71.5,  45.0],
    "WA":      [-124.7, 45.5, -116.9,  49.0],
    "WI":      [ -92.9, 42.5,  -86.8,  47.1],
    "WV":      [ -82.7, 37.2,  -77.7,  40.6],
    "WY":      [-111.1, 40.9, -104.0,  45.1],
}

# Map from config.state values → registry key (only where they differ)
_STATE_TO_KEY = {"GOM": "OFFSHORE"}

MANIFEST_PATH = Path("public/data/wells-manifest.json")


def main() -> None:
    manifest: dict = {"version": 1, "states": {}}

    for meta_path in sorted(Path("public/data").glob("*.meta.json")):
        stem = meta_path.stem.replace(".meta", "")  # wells-nd

        with open(meta_path) as f:
            meta = json.load(f)

        state_code = meta.get("state", "")
        registry_key = _STATE_TO_KEY.get(state_code, state_code)
        count = meta.get("well_count", 0)
        category = meta.get("category", "oil-gas")
        bbox = _BBOXES.get(registry_key)

        if not bbox:
            print(f"  {registry_key}: no bbox configured — skipping")
            continue

        # Prefer .bin over .json for faster loading and 3D support
        bin_path = meta_path.parent / (stem + ".bin")
        json_path = meta_path.parent / (stem + ".json")
        if bin_path.exists():
            ref_file = stem + ".bin"
        elif json_path.exists():
            ref_file = stem + ".json"
        else:
            print(f"  {registry_key}: no data file found — skipping")
            continue

        manifest["states"][registry_key] = {
            "file": ref_file,
            "bbox": bbox,
            "count": count,
            "category": category,
        }
        print(f"  {registry_key}: {ref_file}, {count:,} wells, bbox={bbox}")

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote {MANIFEST_PATH} with {len(manifest['states'])} states")


if __name__ == "__main__":
    main()
