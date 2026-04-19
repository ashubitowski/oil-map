"""
Colorado — CO ECMC Well Spots (shapefile)

Source: Colorado Energy and Carbon Management Commission
  https://ecmc.state.co.us/documents/data/downloads/gis/WELLS_SHP.ZIP
  Updated daily. Contains lat/lon (WGS84), depth (Max_MD), spud date,
  operator, status, and well class in one file — no separate join needed.

Requires: pip install pyshp
"""

import io
import sys
import zipfile
from pathlib import Path
from typing import Iterator, Optional

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

try:
    import shapefile
except ImportError:
    sys.exit("pyshp not installed. Run: pip install pyshp")

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import normalize_api, parse_spud_date, is_in_bounds

WELLS_URL = "https://ecmc.state.co.us/documents/data/downloads/gis/WELLS_SHP.ZIP"

# Colorado FIPS county code (3-digit) → county name
_CO_COUNTIES: dict[str, str] = {
    "001": "Adams", "003": "Alamosa", "005": "Arapahoe", "007": "Archuleta",
    "009": "Baca", "011": "Bent", "013": "Boulder", "014": "Broomfield",
    "015": "Chaffee", "017": "Cheyenne", "019": "Clear Creek", "021": "Conejos",
    "023": "Costilla", "025": "Crowley", "027": "Custer", "029": "Delta",
    "031": "Denver", "033": "Dolores", "035": "Douglas", "037": "Eagle",
    "039": "Elbert", "041": "El Paso", "043": "Fremont", "045": "Garfield",
    "047": "Gilpin", "049": "Grand", "051": "Gunnison", "053": "Hinsdale",
    "055": "Huerfano", "057": "Jackson", "059": "Jefferson", "061": "Kiowa",
    "063": "Kit Carson", "065": "Lake", "067": "La Plata", "069": "Larimer",
    "071": "Las Animas", "073": "Lincoln", "075": "Logan", "077": "Mesa",
    "079": "Mineral", "081": "Moffat", "083": "Montezuma", "085": "Montrose",
    "087": "Morgan", "089": "Otero", "091": "Ouray", "093": "Park",
    "095": "Phillips", "097": "Pitkin", "099": "Prowers", "101": "Pueblo",
    "103": "Rio Blanco", "105": "Rio Grande", "107": "Routt", "109": "Saguache",
    "111": "San Juan", "113": "San Miguel", "115": "Sedgwick", "117": "Summit",
    "119": "Teller", "121": "Washington", "123": "Weld", "125": "Yuma",
}

_config = BaseConfig(
    state="CO",
    source_label="co-ecmc",
    url=WELLS_URL,
    bounds=(37.0, 41.1, -109.1, -102.0),
    output=Path("public/data/wells-co.json"),
    raw_dir=Path("data/raw/co"),
    status_map={
        "AC": "Active",
        "AL": "Active",
        "PR": "Active",
        "EP": "Active",
        "IJ": "Active",
        "DG": "Active",
        "SI": "Inactive",
        "SO": "Inactive",
        "WO": "Inactive",
        "TA": "Inactive",
        "PA": "Plugged & Abandoned",
        "AP": "Permitted",
    },
    well_type_map={
        "OW":  "oil",
        "GW":  "gas",
        "CBM": "gas",
        "OGW": "oil-gas",
        "ERI": "injection",
        "IJ":  "injection",
        "DSP": "disposal",
        "WD":  "disposal",
        "STO": "other",
        "DA":  "other",
        "LO":  "other",
    },
)


class COAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        dest = cfg.raw_dir / "WELLS_SHP.ZIP"
        if dest.exists():
            print(f"  Using cached {dest} (delete to re-download)")
            return dest
        print(f"  Downloading {WELLS_URL} ...")
        resp = requests.get(WELLS_URL, timeout=180, stream=True)
        resp.raise_for_status()
        total = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
                total += len(chunk)
        print(f"  Saved {total / 1e6:.1f} MB → {dest}")
        return dest

    def parse(self, raw: Path) -> Iterator[dict]:
        zf = zipfile.ZipFile(raw)
        r = shapefile.Reader(
            shp=io.BytesIO(zf.read("Wells.shp")),
            dbf=io.BytesIO(zf.read("Wells.dbf")),
        )
        fields = [f[0] for f in r.fields[1:]]
        for rec in r.records():
            yield dict(zip(fields, rec))

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("Latitude") or 0)
            lon = float(row.get("Longitude") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None

        depth_raw = row.get("Max_MD")
        try:
            depth = float(depth_raw) if depth_raw is not None else 0.0
        except (TypeError, ValueError):
            depth = 0.0
        if depth <= 0:
            return None

        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_label = str(row.get("API_Label") or "").strip()
        api = normalize_api(api_label.replace("-", "")) if api_label else None

        county_code = str(row.get("API_County") or "").zfill(3)
        county = _CO_COUNTIES.get(county_code, "Unknown")

        spud_raw = row.get("Spud_Date")
        if hasattr(spud_raw, "isoformat"):
            spud = spud_raw.isoformat()
        else:
            spud = parse_spud_date(str(spud_raw) if spud_raw else "")

        status = cfg.resolve_status(str(row.get("Facil_Stat") or ""))
        well_type = cfg.resolve_well_type(str(row.get("Well_Class") or ""))
        operator = str(row.get("Operator") or "Unknown").strip() or "Unknown"

        well_id = f"co-{normalize_api(api_label.replace('-', ''))}" if api_label else None

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": int(depth),
            "operator": operator,
            "spud_date": spud,
            "status": status,
            "county": county,
            "state": "CO",
            "source": "co-ecmc",
            "well_type": well_type,
        }


adapter = COAdapter(_config)
