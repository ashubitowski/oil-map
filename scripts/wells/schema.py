"""
Shared utilities: field extraction, date parsing, validation, and I/O.
Mirrors the Well shape in lib/types.ts exactly.
"""

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

MANIFEST_PATH = Path("public/data/wells-manifest.json")


def col(row: dict, *names: str) -> str:
    """Return the first matching field value from a row dict, case-insensitive.
    Handles both CSV string dicts and shapefile DBF dicts (native int/float/date values).
    """
    for name in names:
        for key in row:
            if str(key).strip().upper() == name.upper():
                v = row[key]
                if v is None:
                    continue
                if isinstance(v, str):
                    return v.strip()
                return str(v).strip()
    return ""


def col_map(row: dict, field_map: Dict[str, List[str]], canonical: str) -> str:
    """Look up a canonical field using the state's field_map."""
    names = field_map.get(canonical, [canonical])
    return col(row, *names)


def parse_spud_date(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    # YYYYMMDD
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    # YYYY-MM-DD already
    if len(raw) >= 10 and raw[4:5] == "-":
        return raw[:10]
    # MM/DD/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        mo, dy, yr = m.groups()
        return f"{yr}-{mo.zfill(2)}-{dy.zfill(2)}"
    # MM/DD/YY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2})$", raw)
    if m:
        mo, dy, yr = m.groups()
        full_yr = f"20{yr}" if int(yr) < 50 else f"19{yr}"
        return f"{full_yr}-{mo.zfill(2)}-{dy.zfill(2)}"
    # DD-MON-YYYY (e.g. 01-APR-1969) — used by KGS
    MONTHS = {"JAN":"01","FEB":"02","MAR":"03","APR":"04","MAY":"05","JUN":"06",
              "JUL":"07","AUG":"08","SEP":"09","OCT":"10","NOV":"11","DEC":"12"}
    m = re.match(r"(\d{1,2})-([A-Z]{3})-(\d{4})", raw.upper())
    if m:
        dy, mon, yr = m.groups()
        return f"{yr}-{MONTHS.get(mon, '01')}-{dy.zfill(2)}"
    # YYYYMM integer (e.g. 195506 = May 1955) — used by WOGCC WY
    if re.match(r"^\d{6}$", raw):
        yr, mo = raw[:4], raw[4:]
        if 1 <= int(mo) <= 12:
            return f"{yr}-{mo}-01"
    return raw


def normalize_api(api: str) -> str:
    """Strip hyphens/spaces and zero-pad to 10 digits for cross-state joins."""
    cleaned = re.sub(r"[\s\-]", "", api or "")
    if cleaned.isdigit():
        return cleaned.zfill(10)
    return cleaned


def is_in_bounds(lat: float, lon: float, bounds: tuple) -> bool:
    """bounds = (S, N, W, E) in decimal degrees."""
    s, n, w, e = bounds
    return s <= lat <= n and w <= lon <= e


def write_wells(wells: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(wells, f)


def update_manifest(state: str, filename: str, bounds: tuple, count: int, category: str = "oil-gas") -> None:
    """Read-modify-write one state entry in wells-manifest.json."""
    s, n, w, e = bounds
    bbox = [w, s, e, n]  # GeoJSON-style [minLon, minLat, maxLon, maxLat]

    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
    else:
        manifest = {"version": 1, "states": {}}

    entry: dict = {"file": filename, "bbox": bbox, "count": count}
    if category != "oil-gas":
        entry["category"] = category
    manifest["states"][state] = entry

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def write_meta(state: str, source: str, url: str, count: int, output_path: Path) -> None:
    meta_path = output_path.parent / f"{output_path.stem}.meta.json"
    meta = {
        "state": state,
        "source": source,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "well_count": count,
        "url": url,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f)


def print_summary(wells: list, label: str) -> None:
    if not wells:
        print(f"WARNING: 0 {label} wells — check field names in source file")
        return
    depths = [w["depth_ft"] for w in wells]
    types: Dict[str, int] = {}
    for w in wells:
        t = w.get("well_type", "other")
        types[t] = types.get(t, 0) + 1
    print(f"Wrote {len(wells):,} {label} wells")
    print(f"  Depth range: {min(depths):,} – {max(depths):,} ft")
    print(f"  Well types:  {types}")
    counties = {w["county"] for w in wells if w["county"] not in ("", "Unknown")}
    unknown = sum(1 for w in wells if w["county"] in ("", "Unknown"))
    print(f"  Counties: {len(counties)} unique, {unknown} unknown")
