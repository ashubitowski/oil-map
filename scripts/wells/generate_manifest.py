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
    "CA":      [-124.5, 32.5, -114.1,  42.1],
    "CO":      [-109.1, 37.0, -102.0,  41.1],
    "IL":      [ -91.5, 36.9,  -87.5,  42.5],
    "IN":      [ -88.1, 37.8,  -84.8,  41.8],
    "KS":      [-102.1, 37.0,  -94.6,  40.1],
    "KY":      [ -89.6, 36.5,  -81.9,  39.2],
    "LA":      [ -94.1, 28.9,  -89.0,  33.1],
    "MI":      [ -90.5, 41.7,  -82.4,  48.3],
    "MS":      [ -91.7, 30.2,  -88.1,  35.0],
    "MT":      [-116.1, 44.4, -104.0,  49.1],
    "ND":      [-104.1, 45.9,  -96.5,  49.1],
    "NM":      [-109.1, 31.3, -103.0,  37.1],
    "NY":      [ -79.8, 40.5,  -71.9,  45.0],
    "OH":      [ -84.9, 38.4,  -80.5,  42.0],
    "OK":      [-103.0, 33.6,  -94.4,  37.1],
    "OFFSHORE": [-98.0, 23.0,  -80.0,  31.0],
    "PA":      [ -80.5, 39.7,  -74.7,  42.3],
    "TX":      [-106.7, 25.8,  -93.5,  36.5],
    "UT":      [-114.1, 37.0, -109.0,  42.1],
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
        json_name = stem + ".json"                   # wells-nd.json
        json_path = meta_path.parent / json_name

        with open(meta_path) as f:
            meta = json.load(f)

        state_code = meta.get("state", "")
        registry_key = _STATE_TO_KEY.get(state_code, state_code)
        count = meta.get("well_count", 0)
        bbox = _BBOXES.get(registry_key)

        if not bbox:
            print(f"  {registry_key}: no bbox configured — skipping")
            continue
        if not json_path.exists():
            print(f"  {registry_key}: {json_name} missing — skipping")
            continue

        manifest["states"][registry_key] = {"file": json_name, "bbox": bbox, "count": count}
        print(f"  {registry_key}: {json_name}, {count:,} wells, bbox={bbox}")

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote {MANIFEST_PATH} with {len(manifest['states'])} states")


if __name__ == "__main__":
    main()
