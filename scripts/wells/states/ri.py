"""
Rhode Island — Historical Wells and Test Borings (USGS/RI Water Resources Maps)

Source: U.S. Geological Survey — Data release for depth to bedrock from Rhode
  Island Water Resources Maps (DiGiacomo-Cohen & Campbell, 2021)
  https://doi.org/10.5066/P9A1BUKX
  https://www.sciencebase.gov/catalog/item/604bc90bd34eb120311b467b

  8,257 point records digitized from Rhode Island Ground-water maps published
  1948–1964 by the RI Water Resources Coordinating Board et al., in cooperation
  with the USGS. Points include:
    - Wells and test borings penetrating bedrock or unconsolidated deposits
    - USGS observation wells
    - Seismic survey locations
    - Bedrock outcrop points

  Rhode Island has no oil or gas production and no commercial exploration
  history. All wells are water-supply or geotechnical test borings.

Coordinate system: NAD83 State Plane Rhode Island FIPS 3800 (US feet) → WGS84
  Projection: EPSG:3438 (NAD83 / Rhode Island — US feet)

Fields used:
  OBJECTID   — unique record ID
  StationID  — original map station number
  Type       — point type description (well / test boring / seismic / outcrop)
  Symbol     — symbol category (e.g. "Well in bedrock")
  Notes      — supplemental notes (e.g. "altitude of bedrock surface is lower")
  AltitudeBe — altitude in feet of the bedrock surface or bottom of well
               (feet above sea level, NOT depth below surface)
  DataSource — source map code (RI1, RI2, etc.)
  Geometry   — RI State Plane feet, reprojected to WGS84
"""

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator, Optional

try:
    import shapefile
except ImportError:
    sys.exit("pyshp not installed. Run: pip install pyshp")

try:
    from pyproj import Transformer
except ImportError:
    sys.exit("pyproj not installed. Run: pip install pyproj")

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import is_in_bounds

# Direct download URL from ScienceBase
_SHAPEFILE_URL = (
    "https://www.sciencebase.gov/catalog/file/get/"
    "604bc90bd34eb120311b467b"
    "?f=__disk__4c%2Fa8%2Fc7%2F4ca8c7e194f6f19b82482f723753c9468e90e902"
)

# EPSG:3438 = NAD83 / Rhode Island (US feet)
_CRS_RI_STATEPLANE = "EPSG:3438"
_CRS_WGS84 = "EPSG:4326"

# Types to exclude — these are not wells or borings
_EXCLUDE_TYPES = frozenset({
    "Seismic survey location",
    "Bedrock outcrops in areas of outwash or mixed deposits",
})

_config = BaseConfig(
    state="RI",
    source_label="ri-dem",
    category="water-other",
    url=_SHAPEFILE_URL,
    bounds=(41.1, 42.0, -71.9, -71.1),
    output=Path("public/data/wells-ri.json"),
    raw_dir=Path("data/raw/ri"),
    require_depth=False,
    status_map={},
    well_type_map={},
    field_map={},
)


def _download_shapefile(dest_zip: Path) -> None:
    """Download the ScienceBase shapefile ZIP."""
    print("  Fetching RI Water Resources Points shapefile from ScienceBase ...")
    req = urllib.request.Request(
        _SHAPEFILE_URL,
        headers={"User-Agent": "Mozilla/5.0 (oil-map data pipeline)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest_zip.write_bytes(data)
    print(f"  Downloaded {len(data) / 1024:.0f} KB → {dest_zip}")


def _extract_shapefile(zip_path: Path, dest_dir: Path) -> str:
    """Extract the ZIP and return the stem name of the GenericPoints shapefile."""
    stem = "RI_WRpts_GenericPoints"
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.startswith(stem):
                zf.extract(member, dest_dir)
    return stem


class RIAdapter(Adapter):
    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        dest_zip = cfg.raw_dir / "RI_WRpts_shapefiles.zip"
        shp_path = cfg.raw_dir / "ri_wrpts" / "RI_WRpts_GenericPoints.shp"

        if shp_path.exists():
            print(f"  Using cached {shp_path} (delete to re-download)")
        else:
            if not dest_zip.exists():
                _download_shapefile(dest_zip)
            out_dir = cfg.raw_dir / "ri_wrpts"
            _extract_shapefile(dest_zip, out_dir)
            print(f"  Extracted shapefile → {out_dir}")

        return shp_path

    def parse(self, raw: Path) -> Iterator[dict]:
        """Read the shapefile and yield one dict per record with _lat/_lon injected."""
        transformer = Transformer.from_crs(
            _CRS_RI_STATEPLANE, _CRS_WGS84, always_xy=True
        )
        sf = shapefile.Reader(str(raw))
        field_names = [f[0] for f in sf.fields[1:]]

        for sr in sf.shapeRecords():
            attrs = dict(zip(field_names, sr.record))
            pts = sr.shape.points
            if not pts:
                continue
            x, y = pts[0]
            lon, lat = transformer.transform(x, y)
            attrs["_lat"] = lat
            attrs["_lon"] = lon
            yield attrs

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        # Exclude non-well point types
        point_type = str(row.get("Type") or "").strip()
        if point_type in _EXCLUDE_TYPES:
            return None

        try:
            lat = float(row.get("_lat") or 0)
            lon = float(row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        # OBJECTID is guaranteed unique across all 8,257 records.
        # StationID is a per-map number (1–999+) that repeats across maps.
        obj_id = str(row.get("OBJECTID") or "").strip()
        station_id = str(row.get("StationID") or "").strip()
        # Use OBJECTID as primary key; append StationID for readability when present
        if station_id and station_id.lower() not in ("", "<null>", "null"):
            well_id_part = f"{obj_id}-s{station_id}"
        else:
            well_id_part = f"obj{obj_id}"

        # AltitudeBe is altitude of bedrock surface (ft above sea level),
        # not borehole depth — store 0 so require_depth=False passes through.
        depth_ft = 0

        # Classify well type: all are water / test boring, none oil/gas
        well_type = "other"

        # All points from 1948–1964 historical maps; none are active production
        status = "Unknown"

        # No county info in this dataset
        county = "Unknown"

        return {
            "id": f"ri-{well_id_part}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": "Unknown",
            "spud_date": "",
            "status": status,
            "county": county,
            "state": "RI",
            "source": cfg.source_label,
            "well_type": well_type,
        }


adapter = RIAdapter(_config)
