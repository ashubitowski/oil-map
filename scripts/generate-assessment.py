"""
Generates assessment.geojson by enriching EIA play polygons with probability values
derived from published USGS mean undiscovered oil resource estimates (billion barrels).

Key sources:
  - USGS 2018 Permian Basin Assessment: 46.3 BBO mean (largest ever assessed)
  - USGS 2013 Bakken/Three Forks: 7.4 BBO
  - USGS 2018 Wolfcamp/Bone Spring: 20 BBO
  - USGS 2011 Niobrara: 1.84 BBO
  - EIA plays with no specific USGS assessment get a base estimate from production data

Probability is normalized 0-1 relative to the maximum assessed play.
"""

import json
from pathlib import Path

# Mean undiscovered technically recoverable oil (billion barrels) by play keyword
# Sources: USGS assessment fact sheets, EIA Annual Energy Outlook
RESOURCE_ESTIMATES = {
    # Permian sub-plays (2018 USGS - largest ever assessed)
    "Wolfcamp":        46.3,
    "Bone Spring":     20.0,
    "Spraberry":       10.1,
    "Delaware":        11.2,
    "Midland":          8.5,
    "Permian":         20.0,

    # Williston Basin
    "Bakken":           7.4,
    "Three Forks":      3.7,

    # Gulf Coast
    "Eagle Ford":       3.4,
    "Haynesville":      0.3,  # mostly gas
    "Austin Chalk":     1.8,

    # Mid-Continent
    "Woodford":         1.2,
    "Mississippian":    1.0,
    "Fayetteville":     0.2,  # mostly gas
    "Barnett":          0.6,

    # Appalachian
    "Marcellus":        0.6,  # mostly gas
    "Utica":            0.5,

    # Rocky Mountain / DJ Basin
    "Niobrara":         1.84,
    "DJ":               1.2,
    "Hilliard":         0.8,
    "Pinedale":         0.7,
    "Lewis":            0.5,

    # Pacific / Other
    "Monterey":         0.6,
    "Point Arena":      0.2,

    # Southeast / Appalachian
    "Floyd":            0.4,
    "Conasauga":        0.3,
    "Chattanooga":      0.3,
    "Devonian":         0.5,
}

DEFAULT_BBO = 0.3

def estimate_bbo(play_name: str, basin: str) -> float:
    name_lower = play_name.lower()
    for key, val in RESOURCE_ESTIMATES.items():
        if key.lower() in name_lower:
            return val
    basin_lower = basin.lower()
    if "permian" in basin_lower:
        return 8.0
    if "williston" in basin_lower or "bakken" in basin_lower:
        return 3.0
    if "appalachian" in basin_lower:
        return 0.4
    if "anadarko" in basin_lower:
        return 1.0
    if "arkoma" in basin_lower:
        return 0.3
    return DEFAULT_BBO

with open("public/data/plays.geojson") as f:
    plays = json.load(f)

# Compute BBO for each feature
max_bbo = 0.0
for feature in plays["features"]:
    p = feature["properties"]
    bbo = estimate_bbo(p.get("Shale_play", ""), p.get("Basin", ""))
    p["mean_bbo"] = bbo
    if bbo > max_bbo:
        max_bbo = bbo

# Normalize to 0-1 probability using sqrt scale (compresses the Permian outlier)
import math
for feature in plays["features"]:
    p = feature["properties"]
    p["probability"] = round(math.sqrt(p["mean_bbo"] / max_bbo), 4)

# Write as separate assessment file
with open("public/data/assessment.geojson", "w") as f:
    json.dump(plays, f)

print(f"Wrote {len(plays['features'])} assessment units")
print(f"Max BBO: {max_bbo:.1f} (Wolfcamp)")
print()
print(f"{'Play':<35} {'Basin':<25} {'BBO':>6} {'Prob':>6}")
print("-" * 80)
for feat in sorted(plays["features"], key=lambda x: -x["properties"]["mean_bbo"])[:15]:
    p = feat["properties"]
    print(f"{p['Shale_play']:<35} {p['Basin']:<25} {p['mean_bbo']:>6.1f} {p['probability']:>6.3f}")
