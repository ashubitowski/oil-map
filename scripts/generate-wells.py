"""
Generates a realistic synthetic well dataset distributed inside the real EIA play polygons.
Uses play-specific depth ranges and operator profiles based on known industry data.
Run: python3 scripts/generate-wells.py
Output: public/data/wells.json (~1500 wells)
"""

import json
import random
import math
from pathlib import Path

random.seed(42)

# Depth ranges (feet) and dominant operators by play/basin
PLAY_PROFILES = {
    "Wolfcamp": {"min": 7000, "max": 14000, "operators": ["Pioneer Natural Resources", "Occidental Petroleum", "ConocoPhillips", "Chevron", "ExxonMobil XTO"]},
    "Spraberry": {"min": 7500, "max": 11000, "operators": ["Pioneer Natural Resources", "Diamondback Energy", "Laramie Resources", "Fasken Oil"]},
    "Bone Spring": {"min": 8000, "max": 13000, "operators": ["Devon Energy", "Mewbourne Oil", "Cimarex Energy", "Colgate Energy"]},
    "Delaware": {"min": 9000, "max": 14000, "operators": ["Occidental Petroleum", "Coterra Energy", "Centennial Resource", "Percussion Petroleum"]},
    "Midland Basin": {"min": 8500, "max": 13000, "operators": ["Pioneer Natural Resources", "ProPetro Holding", "Double Eagle Energy", "Sable Permian"]},
    "Eagle Ford": {"min": 7000, "max": 13500, "operators": ["EOG Resources", "Marathon Oil", "Callon Petroleum", "BPX Energy", "Murphy Oil"]},
    "Bakken": {"min": 9000, "max": 12000, "operators": ["Continental Resources", "Hess Corporation", "Liberty Resources", "Chord Energy", "Burlington Resources"]},
    "Three Forks": {"min": 9500, "max": 12500, "operators": ["Continental Resources", "Whiting Petroleum", "Oasis Petroleum", "Bruin E&P"]},
    "Barnett": {"min": 6500, "max": 9000, "operators": ["BKV Corp", "Diversified Energy", "DeFord Energy", "Reach Energy"]},
    "Niobrara": {"min": 6000, "max": 9000, "operators": ["Civitas Resources", "PDC Energy", "SRC Energy", "MarkWest Energy"]},
    "DJ Niobrara": {"min": 6500, "max": 8500, "operators": ["Civitas Resources", "Bonanza Creek Energy", "MarkWest Energy"]},
    "Woodford": {"min": 7000, "max": 11000, "operators": ["Continental Resources", "Newpark Resources", "Unit Corporation", "Chaparral Energy"]},
    "Fayetteville": {"min": 1500, "max": 6000, "operators": ["Southwestern Energy", "BHP Petroleum", "SEECO"]},
    "Marcellus": {"min": 5000, "max": 9000, "operators": ["Range Resources", "CNX Resources", "Coterra Energy", "Northeastern Pennsylvania Gas"]},
    "Utica": {"min": 6000, "max": 10000, "operators": ["Encino Energy", "Ascent Resources", "Gulfport Energy", "Harrison Interests"]},
    "Haynesville": {"min": 10000, "max": 14000, "operators": ["Aethon Energy", "Comstock Resources", "Southwestern Energy", "Covey Park Energy"]},
    "default": {"min": 5000, "max": 12000, "operators": ["Halliburton", "Schlumberger", "Baker Hughes", "Range Resources", "Pioneer Natural Resources"]}
}

STATUS_CHOICES = ["Active", "Active", "Active", "Active", "Inactive", "Plugged"]
WELL_TYPES = ["Oil Well", "Oil Well", "Oil Well", "Gas Well", "Oil/Gas Well"]

def get_profile(play_name: str) -> dict:
    for key, profile in PLAY_PROFILES.items():
        if key.lower() in play_name.lower():
            return profile
    return PLAY_PROFILES["default"]

def bbox(geometry) -> tuple:
    """Get bounding box of a geometry."""
    coords = []
    def extract(obj):
        if isinstance(obj, list):
            if obj and isinstance(obj[0], (int, float)):
                coords.append(obj[:2])
            else:
                for item in obj:
                    extract(item)
    extract(geometry["coordinates"])
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return min(lons), min(lats), max(lons), max(lats)

def point_in_polygon_approx(lon: float, lat: float, geometry) -> bool:
    """Ray casting for simple polygon (takes outer ring only)."""
    def get_outer_ring(geom):
        coords = geom["coordinates"]
        if geom["type"] == "Polygon":
            return coords[0]
        elif geom["type"] == "MultiPolygon":
            # use the largest polygon
            largest = max(coords, key=lambda p: len(p[0]))
            return largest[0]
        return []

    ring = get_outer_ring(geometry)
    if not ring:
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][:2]
        xj, yj = ring[j][:2]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-10) + xi):
            inside = not inside
        j = i
    return inside

def sample_points_in_polygon(geometry, n: int) -> list:
    """Sample n random points inside a polygon."""
    minx, miny, maxx, maxy = bbox(geometry)
    points = []
    attempts = 0
    max_attempts = n * 50
    while len(points) < n and attempts < max_attempts:
        lon = random.uniform(minx, maxx)
        lat = random.uniform(miny, maxy)
        if point_in_polygon_approx(lon, lat, geometry):
            points.append((lon, lat))
        attempts += 1
    return points

def format_spud_date() -> str:
    year = random.randint(1990, 2024)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"

def get_county_approx(lat: float, lon: float) -> str:
    """Very rough county assignment based on coordinates."""
    if -105 < lon < -100 and 30 < lat < 33:
        return random.choice(["Midland", "Ector", "Andrews", "Winkler", "Loving", "Ward"])
    if -100 < lon < -96 and 27 < lat < 30:
        return random.choice(["Karnes", "DeWitt", "Gonzales", "Webb", "La Salle", "Dimmit"])
    if -106 < lon < -99 and 46 < lat < 49:
        return random.choice(["Mountrail", "Williams", "McKenzie", "Dunn", "Billings"])
    return "County Unknown"

def get_state(lat: float, lon: float) -> str:
    if -106.6 < lon < -93.5 and 25.8 < lat < 36.5:
        return "TX"
    if -104.1 < lon < -96.4 and 35.9 < lat < 37.1:
        return "KS"
    if -103 < lon < -96.5 and 36.5 < lat < 40:
        return "OK"
    if -104.1 < lon < -96.6 and 40.0 < lat < 43.0:
        return "NE"
    if -105 < lon < -96.5 and 43 < lat < 49:
        return "ND"
    if -109.1 < lon < -104 and 40.9 < lat < 45.0:
        return "WY"
    if -109.1 < lon < -101.9 and 37 < lat < 41:
        return "CO"
    if -116 < lon < -109 and 36.9 < lat < 42:
        return "NV/UT"
    if -76 < lon < -74 and 39 < lat < 42:
        return "PA"
    if -82 < lon < -80 and 38 < lat < 42:
        return "WV/OH"
    if -95 < lon < -88 and 29 < lat < 33.5:
        return "LA"
    return "US"

def wells_for_play(feature, count: int) -> list:
    props = feature["properties"]
    play_name = props.get("Shale_play", "Unknown Play")
    basin = props.get("Basin", "")
    profile = get_profile(play_name)
    points = sample_points_in_polygon(feature["geometry"], count)
    wells = []
    for i, (lon, lat) in enumerate(points):
        depth = random.randint(profile["min"], profile["max"])
        operator = random.choice(profile["operators"])
        state = get_state(lat, lon)
        county = get_county_approx(lat, lon)
        wells.append({
            "id": f"{play_name[:6].upper()}-{abs(hash((lon, lat))) % 100000:05d}",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "depth_ft": depth,
            "operator": operator,
            "spud_date": format_spud_date(),
            "status": random.choice(STATUS_CHOICES),
            "county": county,
            "state": state,
            "play": play_name,
            "basin": basin,
        })
    return wells

# Load the real EIA play polygons
plays_path = Path("public/data/plays.geojson")
with open(plays_path) as f:
    plays = json.load(f)

# Scale wells per play by area (bigger plays get more wells, cap at 80)
all_wells = []
total_area = sum(f["properties"].get("Area_sq_mi", 1000) for f in plays["features"])

for feature in plays["features"]:
    area = feature["properties"].get("Area_sq_mi", 1000)
    # Bias toward oil plays in known productive basins
    play_name = feature["properties"].get("Shale_play", "")
    productive = any(k in play_name for k in ["Wolfcamp", "Bakken", "Eagle Ford", "Spraberry", "Bone Spring", "Delaware", "Barnett", "Niobrara", "Woodford", "Haynesville", "Marcellus", "Utica"])
    base_count = max(5, int((area / total_area) * 2000))
    count = min(80, base_count * 2 if productive else base_count)
    wells = wells_for_play(feature, count)
    all_wells.extend(wells)

print(f"Generated {len(all_wells)} wells across {len(plays['features'])} plays")

# Write output
out_path = Path("public/data/wells.json")
with open(out_path, "w") as f:
    json.dump(all_wells, f)

print(f"Wrote {len(all_wells)} wells to {out_path}")
sample = all_wells[:2]
for w in sample:
    print(f"  {w['id']} | {w['play']:30} | {w['depth_ft']:,} ft | {w['operator']}")
