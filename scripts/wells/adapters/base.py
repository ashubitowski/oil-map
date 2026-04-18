"""
Abstract base class + config dataclass shared by all adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from scripts.wells.schema import (
    col, col_map, parse_spud_date, normalize_api,
    is_in_bounds, write_wells, write_meta, print_summary, update_manifest,
)


@dataclass
class BaseConfig:
    state: str                        # two-letter abbreviation, e.g. "ND"
    source_label: str                 # e.g. "nd-ogic" — matches lib/types.ts Well.source
    bounds: tuple                     # (S, N, W, E) decimal degrees
    output: Path                      # e.g. Path("public/data/wells-nd.json")
    raw_dir: Path                     # e.g. Path("data/raw/nd")
    url: str = ""                     # primary download URL
    raw_filename: str = ""            # override saved filename (default: last segment of URL)
    require_depth: bool = True        # set False for sources that lack depth data
    min_depth_ft: int = 0            # drop wells shallower than this (0 = no filter)
    status_map: dict = field(default_factory=dict)
    well_type_map: dict = field(default_factory=dict)
    field_map: dict = field(default_factory=dict)  # canonical -> [source names]

    def resolve_status(self, raw: str) -> str:
        if not raw:
            return "Unknown"
        return self.status_map.get(raw.strip().upper(), raw.strip() or "Unknown")

    def resolve_well_type(self, raw: str) -> str:
        if not raw:
            return "other"
        return self.well_type_map.get(raw.strip().upper(), "other")


class Adapter(ABC):
    def __init__(self, config: BaseConfig):
        self.config = config

    @abstractmethod
    def download(self) -> Path:
        """Download raw source data; return path to local file. Skip if already cached."""

    @abstractmethod
    def parse(self, raw: Path) -> Iterator[dict]:
        """Yield raw row dicts from the downloaded file."""

    def normalize_row(self, row: dict) -> Optional[dict]:
        """
        Convert a raw row into the canonical Well dict.
        Returns None if the row fails validation (out of bounds, no depth, etc.).
        Subclasses can override for state-specific quirks.
        """
        cfg = self.config
        fm = cfg.field_map

        lat_s = col_map(row, fm, "lat")
        lon_s = col_map(row, fm, "lon")
        depth_s = col_map(row, fm, "depth_ft")

        try:
            lat = float(lat_s)
            lon = float(lon_s)
            depth = float(depth_s)
        except (ValueError, TypeError):
            return None

        if not all(map(lambda x: x == x and x != float("inf"), [lat, lon, depth])):
            return None
        if cfg.require_depth and depth <= 0:
            return None
        if cfg.min_depth_ft > 0 and depth < cfg.min_depth_ft:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api = col_map(row, fm, "api")
        operator = col_map(row, fm, "operator") or "Unknown"
        status = cfg.resolve_status(col_map(row, fm, "status"))
        well_type = cfg.resolve_well_type(col_map(row, fm, "well_type"))
        county = col_map(row, fm, "county") or "Unknown"
        spud = parse_spud_date(col_map(row, fm, "spud_date"))

        well_id = f"{cfg.state.lower()}-{normalize_api(api)}" if api else None
        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": int(depth),
            "operator": operator,
            "spud_date": spud,
            "status": status,
            "county": county,
            "state": cfg.state,
            "source": cfg.source_label,
            "well_type": well_type,
        }

    def apply_base_filters(self, well: dict) -> Optional[dict]:
        """Apply min_depth_ft and any other config-level filters after normalize_row."""
        if self.config.min_depth_ft > 0 and well.get("depth_ft", 0) < self.config.min_depth_ft:
            return None
        return well

    def run(self, dry_run: bool = False, force: bool = False) -> list:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)

        if force:
            raw = self.download()
        else:
            raw = self.download()

        wells = []
        seen: set[str] = set()
        skipped = 0

        for row in self.parse(raw):
            well = self.normalize_row(row)
            if well is None:
                skipped += 1
                continue
            key = well.get("id") or f"{well['lat']},{well['lon']}"
            if key in seen:
                continue
            seen.add(key)
            wells.append(well)

        print(f"  Skipped {skipped:,} invalid rows")
        print_summary(wells, cfg.state)

        if not dry_run:
            write_wells(wells, cfg.output)
            write_meta(cfg.state, cfg.source_label, cfg.url, len(wells), cfg.output)
            update_manifest(cfg.state, cfg.output.name, cfg.bounds, len(wells))
            print(f"  Wrote → {cfg.output}")

        return wells
