"""
Extracts EIA Drilling Productivity Report (DPR) data into two output files:

1. public/data/production-basins.json  — basin centroids + current production (bbl/d)
   Used for sized bubble overlay on the map.

2. public/data/production-history.json — monthly time series per basin (last 3 years)
   Used for the optional timeline slider (Phase 4 stretch goal).

Source: EIA dpr-data.xlsx
Run: python3 scripts/generate-production.py
"""

import openpyxl
import json
from datetime import datetime, date
from pathlib import Path

DPR_PATH = Path("data/raw/dpr-data.xlsx")
OUT_BASINS = Path("public/data/production-basins.json")
OUT_HISTORY = Path("public/data/production-history.json")

# Known basin centroids (lon, lat) for bubble placement
BASIN_META = {
    "Anadarko Region": {
        "display": "Anadarko Basin",
        "lon": -98.5, "lat": 35.5,
        "states": ["OK", "KS", "TX"],
        "color": "#f59e0b",
    },
    "Appalachia Region": {
        "display": "Appalachian Basin",
        "lon": -80.2, "lat": 40.0,
        "states": ["PA", "WV", "OH"],
        "color": "#10b981",
    },
    "Bakken Region": {
        "display": "Bakken",
        "lon": -103.0, "lat": 47.5,
        "states": ["ND", "MT"],
        "color": "#3b82f6",
    },
    "Eagle Ford Region": {
        "display": "Eagle Ford",
        "lon": -98.5, "lat": 28.8,
        "states": ["TX"],
        "color": "#f97316",
    },
    "Haynesville Region": {
        "display": "Haynesville",
        "lon": -93.5, "lat": 32.2,
        "states": ["LA", "TX"],
        "color": "#8b5cf6",
    },
    "Niobrara Region": {
        "display": "Niobrara / DJ Basin",
        "lon": -104.5, "lat": 41.0,
        "states": ["CO", "WY"],
        "color": "#ec4899",
    },
    "Permian Region": {
        "display": "Permian Basin",
        "lon": -102.0, "lat": 31.8,
        "states": ["TX", "NM"],
        "color": "#ef4444",
    },
}

wb = openpyxl.load_workbook(str(DPR_PATH))

basins = []
history = {}

for sheet_name, meta in BASIN_META.items():
    if sheet_name not in wb.sheetnames:
        continue
    ws = wb[sheet_name]

    rows = list(ws.iter_rows(min_row=3, values_only=True))  # skip 2-row header
    # Col index: 0=Month, 1=Rig count, 2=Prod/rig, 3=Legacy change, 4=Total oil production (bbl/d)
    monthly = []
    for row in rows:
        if not row[0] or not isinstance(row[0], datetime):
            continue
        dt = row[0]
        oil_total = row[4]
        if oil_total is None:
            continue
        monthly.append({
            "month": dt.strftime("%Y-%m"),
            "bpd": round(float(oil_total)),
        })

    if not monthly:
        continue

    # Most recent valid reading
    latest = monthly[-1]

    basins.append({
        "id": sheet_name.replace(" ", "_").lower(),
        "name": meta["display"],
        "lon": meta["lon"],
        "lat": meta["lat"],
        "states": meta["states"],
        "color": meta["color"],
        "bpd": latest["bpd"],
        "month": latest["month"],
    })

    # Last 36 months for history
    history[meta["display"]] = monthly[-36:]

# Sort by production descending
basins.sort(key=lambda x: -x["bpd"])

with open(OUT_BASINS, "w") as f:
    json.dump(basins, f, indent=2)

with open(OUT_HISTORY, "w") as f:
    json.dump(history, f)

print(f"Wrote {len(basins)} basins to {OUT_BASINS}")
print(f"Wrote history ({len(history)} basins) to {OUT_HISTORY}")
print()
print(f"{'Basin':<25} {'Production (bbl/d)':>20} {'Month'}")
print("-" * 55)
for b in basins:
    print(f"{b['name']:<25} {b['bpd']:>20,} {b['month']}")
