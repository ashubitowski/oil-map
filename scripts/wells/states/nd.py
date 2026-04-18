"""
North Dakota — NDIC well data (shapefile ZIP).

Source: ND Oil and Gas Division GIS downloads (public, no auth)
  https://gis.dmr.nd.gov/downloads/oilgas/shapefile/OGD_Wells.zip
  (verified 2026-04; browse at https://gis.dmr.nd.gov/)

Requires: pip install pyshp

The ZIP contains OGD_Wells.shp + OGD_Wells.dbf. pyshp reads both and yields
(geometry_point, attribute_dict) pairs. Lat/lon come from the point geometry;
other fields come from the DBF attributes.
"""

import sys
import zipfile
import io
from pathlib import Path
from typing import Iterator, Optional

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")
try:
    import shapefile  # pyshp
except ImportError:
    sys.exit("pyshp not installed. Run: pip install pyshp")

from scripts.wells.adapters.direct_download import DirectDownloadAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import col, parse_spud_date

COUNTY_FIPS = {
    "001": "Adams", "003": "Barnes", "005": "Benson", "007": "Billings",
    "009": "Bottineau", "011": "Bowman", "013": "Burke", "015": "Burleigh",
    "017": "Cass", "019": "Cavalier", "021": "Dickey", "023": "Divide",
    "025": "Dunn", "027": "Eddy", "029": "Emmons", "031": "Foster",
    "033": "Golden Valley", "035": "Grand Forks", "037": "Grant", "039": "Griggs",
    "041": "Hettinger", "043": "Kidder", "045": "La Moure", "047": "Logan",
    "049": "McHenry", "051": "McIntosh", "053": "McKenzie", "055": "McLean",
    "057": "Mercer", "059": "Morton", "061": "Mountrail", "063": "Nelson",
    "065": "Oliver", "067": "Pembina", "069": "Pierce", "071": "Ramsey",
    "073": "Ransom", "075": "Renville", "077": "Richland", "079": "Rolette",
    "081": "Sargent", "083": "Sheridan", "085": "Sioux", "087": "Slope",
    "089": "Stark", "091": "Steele", "093": "Stutsman", "095": "Towner",
    "097": "Traill", "099": "Walsh", "101": "Ward", "103": "Wells",
    "105": "Williams",
}

_config = BaseConfig(
    state="ND",
    source_label="nd-ogic",
    url="https://gis.dmr.nd.gov/downloads/oilgas/shapefile/OGD_Wells.zip",
    bounds=(45.9, 49.1, -104.1, -96.5),
    output=Path("public/data/wells-nd.json"),
    raw_dir=Path("data/raw/nd"),
    status_map={
        "A": "Active", "I": "Inactive", "P": "Plugged", "D": "Drilled",
        "C": "Completed", "PA": "Plugged & Abandoned", "TA": "Temporarily Abandoned",
        "Active": "Active", "Inactive": "Inactive", "Plugged": "Plugged & Abandoned",
    },
    well_type_map={
        "O": "oil", "OW": "oil", "OIL": "oil",
        "G": "gas", "GW": "gas", "GAS": "gas",
        "OG": "oil-gas", "OIL AND GAS": "oil-gas",
        "WD": "disposal", "WI": "injection",
        "I": "injection", "D": "disposal",
    },
    field_map={},  # not used — NDAdapter overrides parse() for shapefile
)


class NDAdapter(DirectDownloadAdapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        dest = cfg.raw_dir / "OGD_Wells.zip"
        if dest.exists():
            print(f"  Using cached {dest} (delete to re-download)")
            return dest
        print(f"  Downloading {cfg.url} ...")
        resp = requests.get(cfg.url, timeout=180, stream=True)
        resp.raise_for_status()
        total = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
                total += len(chunk)
        print(f"  Saved {total / 1e6:.1f} MB → {dest}")
        return dest

    def parse(self, raw: Path) -> Iterator[dict]:
        """Read shapefile from ZIP and yield attribute dicts with _lat/_lon injected."""
        with zipfile.ZipFile(raw) as zf:
            names = zf.namelist()
            shp_names = [n for n in names if n.lower().endswith(".shp")]
            dbf_names = [n for n in names if n.lower().endswith(".dbf")]
            shx_names = [n for n in names if n.lower().endswith(".shx")]
            if not shp_names or not dbf_names:
                raise RuntimeError(f"No shapefile in {raw}. Contents: {names}")
            print(f"  Reading shapefile {shp_names[0]} from ZIP ...")
            shp_data = zf.read(shp_names[0])
            dbf_data = zf.read(dbf_names[0])
            shx_data = zf.read(shx_names[0]) if shx_names else b""

        sf = shapefile.Reader(
            shp=io.BytesIO(shp_data),
            dbf=io.BytesIO(dbf_data),
            shx=io.BytesIO(shx_data) if shx_data else None,
        )
        field_names = [f[0] for f in sf.fields[1:]]  # skip DeletionFlag
        print(f"  DBF fields ({len(field_names)}): {', '.join(field_names[:12])} ...")
        count = 0
        for shape_rec in sf.iterShapeRecords():
            geom = shape_rec.shape
            rec = shape_rec.record
            row = dict(zip(field_names, rec))
            if geom.shapeType != 0 and hasattr(geom, "points") and geom.points:
                row["_lon"], row["_lat"] = geom.points[0]
            count += 1
            yield row
        print(f"  Shapefile: {count:,} records")

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config
        import math
        from scripts.wells.schema import col, is_in_bounds, normalize_api, parse_spud_date

        # col() does case-insensitive lookup so lowercase DBF keys work fine
        lat_raw = col(row, "_lat", "latitude", "lat")
        lon_raw = col(row, "_lon", "longitude", "lon")
        # ND shapefile uses "td" (total depth) as the depth field
        depth_raw = col(row, "td", "depth", "td_ft", "total_depth", "measured_d", "current_m")

        try:
            lat, lon, depth = float(lat_raw or 0), float(lon_raw or 0), float(depth_raw or 0)
        except (ValueError, TypeError):
            return None

        if not all(math.isfinite(v) for v in [lat, lon, depth]):
            return None
        if depth <= 0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api = col(row, "api_no", "api", "api_number", "api_well_n")
        operator = col(row, "operator", "curr_operator") or "Unknown"
        status_raw = col(row, "status", "well_statu", "well_status")
        well_type_raw = col(row, "well_type", "type")
        county_name = col(row, "County", "county", "county_name")
        county_fips_raw = col(row, "county_cod", "county_code", "county_fip")

        # spud_date in this shapefile comes back as datetime.date — convert to ISO string
        spud_val = row.get("spud_date")
        if spud_val and hasattr(spud_val, "strftime"):
            spud = spud_val.strftime("%Y-%m-%d")
        else:
            spud = parse_spud_date(str(spud_val or ""))

        county = county_name or COUNTY_FIPS.get(str(county_fips_raw).zfill(3), "Unknown")
        status = cfg.resolve_status(status_raw)
        well_type = cfg.resolve_well_type(well_type_raw)

        return {
            "id": f"nd-{normalize_api(api)}" if api else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": int(depth),
            "operator": operator,
            "spud_date": spud,
            "status": status,
            "county": county,
            "state": "ND",
            "source": "nd-ogic",
            "well_type": well_type,
        }


adapter = NDAdapter(_config)
