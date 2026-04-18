"""
Converts USGS Shale Gas Assessment Unit shapefiles to a merged GeoJSON.
Assigns probability values based on AU name and USGS published resource estimates.

Run: python3 scripts/convert-usgs-au.py
Output: public/data/assessment.geojson
"""

import shapefile
import json
import math
from pathlib import Path

RAW_DIR = Path("data/raw/shale-gas-au")
OUT_PATH = Path("public/data/assessment.geojson")

# USGS published mean undiscovered technically recoverable gas/oil by AU
# Gas in TCF, converted to relative probability. Marcellus ~97 TCF, Barnett ~44 TCF, etc.
# For oil-equivalent probability, using relative resource size
AU_RESOURCES = {
    "Marcellus":     97.0,
    "Utica":         38.0,
    "AppalachianDev": 10.0,
    "Haynesville":   74.8,
    "Bossier":       20.0,
    "EagleFord":     22.0,
    "Pearsall":       3.0,
    "Barnett":       44.3,
    "Woodford":      25.0,
    "WoodfordBarnett": 15.0,
    "Atoka":          5.0,
    "Fayetteville":  31.9,
    "Caney":          2.0,
    "Niobrara":      66.0,
    "CaneCrk":        6.0,
    "GothicChimRkHov": 4.0,
    "Antrim":         3.5,
    "NewAlbany":      2.0,
    "Chattanooga":    2.0,
    "Shublik":       15.0,
    "Brookian":       8.0,
}

def get_resource(au_name: str) -> float:
    for key, val in AU_RESOURCES.items():
        if key.lower() in au_name.lower():
            return val
    return 2.0

def read_shp(shp_path: Path) -> list:
    """Read a shapefile and return list of (geometry_geojson, properties_dict)."""
    try:
        sf = shapefile.Reader(str(shp_path))
        fields = [f[0] for f in sf.fields[1:]]  # skip DeletionFlag
        features = []
        for shape_rec in sf.shapeRecords():
            geom = shape_rec.shape.__geo_interface__
            props = dict(zip(fields, shape_rec.record))
            # Convert bytes to str if needed
            props = {k: v.strip() if isinstance(v, str) else v for k, v in props.items()}
            features.append((geom, props))
        return features
    except Exception as e:
        print(f"  Error reading {shp_path.name}: {e}")
        return []

# Find all unique base shapefiles (one per AU)
shp_files = sorted(set(RAW_DIR.glob("*.shp")))
print(f"Found {len(shp_files)} USGS assessment unit shapefiles")

all_features = []
max_resource = 0.0

for shp_file in shp_files:
    au_name = shp_file.stem  # e.g. "au50670467Marcellus"
    # Extract readable name from filename (after the numeric ID)
    display_name = ''.join(c if not c.isdigit() else ' ' for c in au_name.replace('au', '')).strip()
    # Better: just use the part after the numbers
    import re
    # au50670467Marcellus → "Marcellus" (skip "au" prefix + digits)
    match = re.search(r'au\d+([A-Za-z].*)$', au_name)
    raw = match.group(1) if match else au_name
    # CamelCase → spaced: "EagleFord" → "Eagle Ford"
    readable = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', raw)

    records = read_shp(shp_file)
    resource = get_resource(readable)
    if resource > max_resource:
        max_resource = resource

    for geom, props in records:
        props["AU_name"] = readable
        props["AU_file"] = au_name
        props["mean_resource_tcf"] = resource
        all_features.append({"geom": geom, "props": props})

# Normalize to 0-1 probability
print(f"Max resource: {max_resource} TCF (Marcellus)")
print(f"Total AUs: {len(all_features)}")

def trim_coords(obj, precision=4):
    """Recursively round coordinates to reduce file size."""
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(c, precision) for c in obj]
        return [trim_coords(item, precision) for item in obj]
    return obj

features_out = []
for item in all_features:
    prob = round(math.sqrt(item["props"]["mean_resource_tcf"] / max_resource), 4)
    geom = item["geom"].copy()
    geom["coordinates"] = trim_coords(geom["coordinates"])
    feature = {
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "AU_name": item["props"]["AU_name"],
            "Shale_play": item["props"]["AU_name"],
            "mean_resource_tcf": item["props"]["mean_resource_tcf"],
            "probability": prob,
        }
    }
    features_out.append(feature)

geojson = {
    "type": "FeatureCollection",
    "features": features_out,
}

with open(OUT_PATH, "w") as f:
    json.dump(geojson, f)

print(f"\nWrote {len(features_out)} features to {OUT_PATH}")
print(f"\nTop 10 by resource:")
sorted_f = sorted(features_out, key=lambda x: -x["properties"]["mean_resource_tcf"])
for f in sorted_f[:10]:
    p = f["properties"]
    print(f"  {p['AU_name']:<30} {p['mean_resource_tcf']:>6.1f} TCF  prob={p['probability']:.3f}")
