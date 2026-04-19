"""
Oklahoma — OCC RBDMS Well Data + Completions join

Primary:    https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/rbdms-wells.csv
            Nightly update. ~455k wells. Fields: API, lat, lon, operator, county, status, type.

Secondary:  https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/completions-wells-formations-base.xlsx
            Daily update. ~202k rows. Provides Total_Depth + Spud date joined by API.

Requires: pip install requests
"""

import csv
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, Optional

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

from scripts.wells.adapters.base import Adapter, BaseConfig
from scripts.wells.schema import normalize_api, parse_spud_date, is_in_bounds

RBDMS_URL = "https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/rbdms-wells.csv"
COMPLETIONS_URL = "https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/completions-wells-formations-base.xlsx"

_XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

_config = BaseConfig(
    state="OK",
    source_label="ok-occ",
    url=RBDMS_URL,
    bounds=(33.6, 37.1, -103.0, -94.4),
    output=Path("public/data/wells-ok.json"),
    raw_dir=Path("data/raw/ok"),
    require_depth=False,
    status_map={
        "AC": "Active",
        "ACRT": "Active",
        "DRL": "Active",
        "TA": "Inactive",
        "TM": "Inactive",
        "STFD": "Inactive",
        "EX": "Inactive",
        "OR": "Inactive",
        "SFFO": "Inactive",
        "SFAW": "Inactive",
        "SIFORDER": "Inactive",
        "PA": "Plugged & Abandoned",
        "PAFF": "Plugged & Abandoned",
        "PASF": "Plugged & Abandoned",
        "PASUR": "Plugged & Abandoned",
        "PASURSF": "Plugged & Abandoned",
        "NE": "Permitted",
        "SP": "Permitted",
        "ND": "Permitted",
    },
    well_type_map={
        "OIL": "oil",
        "OG": "oil-gas",
        "OIL": "oil",
        "GAS": "gas",
        "GAS": "gas",
        "INJ": "injection",
        "2RIN": "injection",
        "2RI": "injection",
        "WIW": "injection",
        "2RSI": "injection",
        "2R": "injection",
        "SWD": "disposal",
        "WSW": "disposal",
        "SW": "disposal",
        "GSW": "disposal",
        "LPSW": "disposal",
        "DRY": "other",
        "NT": "other",
        "TM": "other",
        "DUC": "other",
        "OBS": "other",
        "SCO": "other",
    },
)


def _col_letter_to_index(col: str) -> int:
    """Convert Excel column letter(s) to 0-based index. A=0, Z=25, AA=26."""
    result = 0
    for ch in col.upper():
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def _cell_col(ref: str) -> str:
    """Extract column letter(s) from cell ref like 'BZ42'."""
    return "".join(ch for ch in ref if ch.isalpha())


def _build_depth_index(path: Path) -> dict:
    """
    Returns {api_str: (depth_ft, spud_date)} from completions XLSX.
    Multiple completions per well — keeps the max depth and earliest non-null spud.
    """
    zf = zipfile.ZipFile(path)

    # Load shared strings table
    ss_tree = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in ss_tree.iter(f"{{{_XLSX_NS}}}si"):
        parts = [t.text or "" for t in si.iter(f"{{{_XLSX_NS}}}t")]
        strings.append("".join(parts))

    index: dict[str, tuple[int, str]] = {}  # api -> (depth_ft, spud_date)

    # Column letter → field name (populated from header row)
    col_map: dict[str, str] = {}
    TARGET = {"API_Number", "Total_Depth", "Spud"}
    header_done = False

    with zf.open("xl/worksheets/sheet1.xml") as ws_file:
        for event, elem in ET.iterparse(ws_file, events=["end"]):
            if elem.tag != f"{{{_XLSX_NS}}}row":
                continue

            cells: dict[str, str] = {}
            for c in elem.findall(f"{{{_XLSX_NS}}}c"):
                ref = c.get("r", "")
                col_letter = _cell_col(ref)
                t = c.get("t", "")
                v = c.find(f"{{{_XLSX_NS}}}v")
                if v is not None and v.text:
                    cells[col_letter] = strings[int(v.text)] if t == "s" else v.text
                else:
                    cells[col_letter] = ""

            if not header_done:
                for letter, name in cells.items():
                    if name in TARGET:
                        col_map[letter] = name
                header_done = True
                elem.clear()
                continue

            api_col = next((l for l, n in col_map.items() if n == "API_Number"), None)
            depth_col = next((l for l, n in col_map.items() if n == "Total_Depth"), None)
            spud_col = next((l for l, n in col_map.items() if n == "Spud"), None)

            api = cells.get(api_col or "", "").strip() if api_col else ""
            if not api:
                elem.clear()
                continue

            depth_raw = cells.get(depth_col or "", "") if depth_col else ""
            spud_raw = cells.get(spud_col or "", "") if spud_col else ""

            try:
                depth = int(float(depth_raw)) if depth_raw else 0
            except (ValueError, TypeError):
                depth = 0
            if depth > 35000:  # cap implausible values (deepest OK well ~31k ft)
                depth = 0

            # Filter Excel's null date sentinel
            spud = ""
            if spud_raw and not spud_raw.startswith("1900-"):
                spud = spud_raw[:10]

            existing = index.get(api)
            if existing is None:
                index[api] = (depth, spud)
            else:
                prev_depth, prev_spud = existing
                new_depth = max(prev_depth, depth)
                new_spud = spud if (not prev_spud and spud) else prev_spud
                index[api] = (new_depth, new_spud)

            elem.clear()

    print(f"  Depth index: {len(index):,} unique APIs from completions")
    return index


class OKAdapter(Adapter):
    _depth_index: dict

    def download(self) -> Path:
        cfg = self.config
        cfg.raw_dir.mkdir(parents=True, exist_ok=True)

        rbdms_path = cfg.raw_dir / "rbdms-wells.csv"
        completions_path = cfg.raw_dir / "ok-completions.xlsx"

        if not rbdms_path.exists():
            print(f"  Downloading RBDMS wells CSV ...")
            resp = requests.get(RBDMS_URL, timeout=180, stream=True)
            resp.raise_for_status()
            with open(rbdms_path, "wb") as f:
                for chunk in resp.iter_content(65536):
                    f.write(chunk)
            print(f"  Saved → {rbdms_path}")
        else:
            print(f"  Using cached {rbdms_path}")

        if not completions_path.exists():
            print(f"  Downloading completions XLSX (~72MB) ...")
            resp = requests.get(COMPLETIONS_URL, timeout=300, stream=True)
            resp.raise_for_status()
            total = 0
            with open(completions_path, "wb") as f:
                for chunk in resp.iter_content(65536):
                    f.write(chunk)
                    total += len(chunk)
            print(f"  Saved {total / 1e6:.1f} MB → {completions_path}")
        else:
            print(f"  Using cached {completions_path}")

        return rbdms_path

    def parse(self, raw: Path) -> Iterator[dict]:
        completions_path = self.config.raw_dir / "ok-completions.xlsx"
        print("  Building depth index from completions ...")
        self._depth_index = _build_depth_index(completions_path)
        with open(raw, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            yield from reader

    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("SH_LAT") or 0)
            lon = float(row.get("SH_LON") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API") or "").strip()
        if not api_raw:
            return None

        depth_info = self._depth_index.get(api_raw, (0, ""))
        depth_ft, spud_date = depth_info

        county = str(row.get("COUNTY") or "Unknown").strip().title()
        operator = str(row.get("OPERATOR") or "Unknown").strip() or "Unknown"
        status = cfg.resolve_status(str(row.get("WELLSTATUS") or ""))
        well_type_raw = str(row.get("WELLTYPE") or "").strip().upper()
        # Normalize common variants
        well_type_raw = well_type_raw.replace("2RIN", "2RIN").replace("2RI", "2RI")
        well_type = cfg.resolve_well_type(well_type_raw)

        well_id = f"ok-{normalize_api(api_raw)}"

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "OK",
            "source": "ok-occ",
            "well_type": well_type,
        }


adapter = OKAdapter(_config)
