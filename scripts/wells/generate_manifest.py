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
    "ND":      [-104.1, 45.9,  -96.5,  49.1],
    "CO":      [-109.1, 37.0, -102.0,  41.1],
    "KS":      [-102.1, 37.0,  -94.6,  40.1],
    "WY":      [-111.1, 40.9, -104.0,  45.1],
    "NM":      [-109.1, 31.3, -103.0,  37.1],
    "CA":      [-124.5, 32.5, -114.1,  42.1],
    "OFFSHORE": [-98.0, 23.0,  -80.0,  31.0],
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
