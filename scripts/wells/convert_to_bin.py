"""
One-shot conversion: reads existing wells-*.json files and writes wells-*.bin,
then updates wells-manifest.json to point at the new binary files.

Usage:
  python3 scripts/wells/convert_to_bin.py [STATE ...]

  python3 scripts/wells/convert_to_bin.py          # convert all states in manifest
  python3 scripts/wells/convert_to_bin.py ND KS    # convert specific states only
"""

import json
import sys
import time
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.wells.binary import write_wells_bin
from scripts.wells.generate_manifest import MANIFEST_PATH


def convert_state(state_key: str, entry: dict) -> dict:
    # Source is always the .json file; entry["file"] may already be .bin
    stem      = Path(entry["file"]).stem.removesuffix("")
    json_name = Path(entry["file"]).with_suffix(".json").name
    json_path = Path("public/data") / json_name
    bin_name  = Path(entry["file"]).with_suffix(".bin").name
    bin_path  = Path("public/data") / bin_name

    if not json_path.exists():
        print(f"  {state_key}: {json_path} not found — skipping")
        return entry

    print(f"  {state_key}: reading {json_path} ({json_path.stat().st_size / 1e6:.1f} MB)...")
    t0 = time.time()
    with open(json_path) as f:
        wells = json.load(f)
    print(f"    parsed {len(wells):,} wells in {time.time() - t0:.1f}s")

    t1 = time.time()
    write_wells_bin(wells, bin_path)
    elapsed = time.time() - t1
    size_mb = bin_path.stat().st_size / 1e6
    print(f"    wrote {bin_path} ({size_mb:.1f} MB) in {elapsed:.1f}s")

    return {**entry, "file": bin_name}


def main() -> None:
    if not MANIFEST_PATH.exists():
        print(f"ERROR: {MANIFEST_PATH} not found. Run `npm run generate:manifest` first.")
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    filter_states = {s.upper() for s in sys.argv[1:]} if len(sys.argv) > 1 else None

    updated = False
    for key, entry in manifest["states"].items():
        if filter_states and key not in filter_states:
            continue
        if entry["file"].endswith(".bin"):
            bin_path = Path("public/data") / entry["file"]
            if bin_path.exists():
                print(f"  {key}: already .bin — skipping (delete {entry['file']} to reconvert)")
                continue
        new_entry = convert_state(key, entry)
        if new_entry["file"] != entry["file"]:
            manifest["states"][key] = new_entry
            updated = True

    if updated:
        with open(MANIFEST_PATH, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nUpdated {MANIFEST_PATH}")
    else:
        print("\nNo changes — manifest unchanged")


if __name__ == "__main__":
    main()
