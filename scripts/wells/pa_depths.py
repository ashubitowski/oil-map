"""
Build a PADEP permit → depth_ft lookup from FracFocus bulk data.

FracFocus (fracfocusdata.org) is the disclosure registry for hydraulically
fractured wells in the US. PA Marcellus/Utica shale wells are almost all in
there with TotalVerticalDepth populated.

Join strategy: FracFocus API numbers for PA look like "3706523453" where
  37 = PA state code, 065 = county FIPS, 23453 = well number.
The PADEP PERMIT_NUM is "065-23453" — same county + well number, different
separator. We reconstruct a canonical "CCC-NNNNN" key from both sides.

Run once; output is cached at data/raw/pa/pa_depths.json.
Delete the file to re-download.

Usage:
    python3 scripts/wells/pa_depths.py
"""

import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

FRACFOCUS_URL = "https://www.fracfocusdata.org/digitaldownload/FracFocusCSV.zip"
OUT = Path("data/raw/pa/pa_depths.json")
PA_STATE = "37"


def _api_to_permit(api: str) -> str | None:
    """
    Convert FracFocus API number to a PADEP-style permit key "CCC-NNNNN".

    FracFocus stores API as a 10-digit string: SSCCCPPPPP
      SS  = state (37 for PA)
      CCC = county FIPS (3 digits)
      PPPPP = well/permit number (5 digits, may be zero-padded)

    PADEP PERMIT_NUM format: "CCC-NNNNN" where NNNNN is NOT zero-padded.
    """
    api = api.strip().replace("-", "").replace(" ", "")
    if len(api) < 10 or not api.startswith(PA_STATE):
        return None
    county = api[2:5]
    well_raw = api[5:10]
    # strip leading zeros to match PADEP's format
    well = str(int(well_raw)) if well_raw.isdigit() else well_raw
    return f"{county}-{well}"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    if OUT.exists():
        data = json.loads(OUT.read_text())
        print(f"  Cached: {len(data):,} PA depth records at {OUT}  (delete to re-fetch)")
        return

    print(f"  Downloading FracFocus CSV from {FRACFOCUS_URL} ...")
    print("  (this is ~430 MB — will take a minute)")

    depths: dict[str, int] = {}

    with urllib.request.urlopen(FRACFOCUS_URL, timeout=300) as resp:
        raw = resp.read()

    print(f"  Downloaded {len(raw) / 1e6:.0f} MB; scanning PA records ...")

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        csv_files = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        print(f"  {len(csv_files)} CSV file(s) in archive")

        for fname in csv_files:
            with zf.open(fname) as fh:
                reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace"))
                for row in reader:
                    state = (row.get("StateNumber") or row.get("state_number") or "").strip()
                    if state != PA_STATE:
                        continue

                    api = row.get("APINumber") or row.get("api_number") or ""
                    permit = _api_to_permit(api)
                    if not permit:
                        continue

                    raw_depth = row.get("TotalVerticalDepth") or row.get("total_vertical_depth") or ""
                    try:
                        depth = int(float(raw_depth.strip()))
                    except (ValueError, AttributeError):
                        continue

                    if depth > 0:
                        # Keep deepest value if permit appears more than once
                        if depth > depths.get(permit, 0):
                            depths[permit] = depth

    print(f"  Matched {len(depths):,} PA wells with depth data")
    OUT.write_text(json.dumps(depths, indent=2))
    print(f"  Saved → {OUT}")

    # Quick sanity check
    if depths:
        sample = sorted(depths.items(), key=lambda x: -x[1])[:5]
        print("  Deepest wells:")
        for permit, d in sample:
            print(f"    {permit}: {d:,} ft")


if __name__ == "__main__":
    main()
