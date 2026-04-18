"""
Kansas — KGS (Kansas Geological Survey) oil and gas wells archive.

Source: KGS Petroleum Research Section
  https://www.kgs.ku.edu/PRS/petroDB.html
  Direct ZIP: https://www.kgs.ku.edu/PRS/Ora_Archive/ks_wells.zip
  Verified 2026-04

~437k total wells (all historical). County is parsed from the API number
(format 15-XXX-YYYYY where XXX is the county FIPS code). Well type is
inferred from IP_OIL / IP_GAS columns; defaults to "other" when unknown.

Spud dates are in DD-MON-YYYY format (e.g. 01-APR-1969).
"""

import re
from pathlib import Path
from typing import Optional
from scripts.wells.adapters.direct_download import DirectDownloadAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import col, parse_spud_date, normalize_api, is_in_bounds

COUNTY_FIPS = {
    "001":"Allen","003":"Anderson","005":"Atchison","007":"Barton","009":"Bourbon",
    "011":"Brown","013":"Butler","015":"Chase","017":"Chautauqua","019":"Cherokee",
    "021":"Cheyenne","023":"Clark","025":"Clay","027":"Cloud","029":"Coffey",
    "031":"Comanche","033":"Cowley","035":"Crawford","037":"Decatur","039":"Dickinson",
    "041":"Doniphan","043":"Douglas","045":"Edwards","047":"Elk","049":"Ellis",
    "051":"Ellsworth","053":"Finney","055":"Ford","057":"Franklin","059":"Geary",
    "061":"Gove","063":"Graham","065":"Grant","067":"Gray","069":"Greeley",
    "071":"Greenwood","073":"Hamilton","075":"Harper","077":"Harvey","079":"Haskell",
    "081":"Hodgeman","083":"Jackson","085":"Jefferson","087":"Jewell","089":"Johnson",
    "091":"Kearny","093":"Kingman","095":"Kiowa","097":"Labette","099":"Lane",
    "101":"Leavenworth","103":"Lincoln","105":"Linn","107":"Logan","109":"Lyon",
    "111":"McPherson","113":"Marion","115":"Marshall","117":"Meade","119":"Miami",
    "121":"Mitchell","123":"Montgomery","125":"Morris","127":"Morton","129":"Nemaha",
    "131":"Neosho","133":"Ness","135":"Norton","137":"Osage","139":"Osborne",
    "141":"Ottawa","143":"Pawnee","145":"Phillips","147":"Pottawatomie","149":"Pratt",
    "151":"Rawlins","153":"Reno","155":"Republic","157":"Rice","159":"Riley",
    "161":"Rooks","163":"Rush","165":"Russell","167":"Saline","169":"Scott",
    "171":"Sedgwick","173":"Seward","175":"Shawnee","177":"Sheridan","179":"Sherman",
    "181":"Smith","183":"Stafford","185":"Stanton","187":"Stevens","189":"Sumner",
    "191":"Thomas","193":"Trego","195":"Wabaunsee","197":"Wallace","199":"Washington",
    "201":"Wichita","203":"Wilson","205":"Woodson","207":"Wyandotte",
}

_config = BaseConfig(
    state="KS",
    source_label="ks-kgs",
    url="https://www.kgs.ku.edu/PRS/Ora_Archive/ks_wells.zip",
    raw_filename="ks_wells.zip",
    min_depth_ft=2000,
    bounds=(37.0, 40.1, -102.1, -94.6),
    output=Path("public/data/wells-ks.json"),
    raw_dir=Path("data/raw/ks"),
    status_map={
        "A": "Active", "AB": "Active", "ACT": "Active",
        "I": "Inactive", "P": "Plugged", "PA": "Plugged & Abandoned",
        "D&A": "Plugged & Abandoned", "TA": "Temporarily Abandoned",
        "D": "Drilling", "PR": "Permitted",
    },
    well_type_map={},  # not used — KSAdapter infers from IP_OIL/IP_GAS
    field_map={
        "lat": ["LATITUDE"],
        "lon": ["LONGITUDE"],
        "depth_ft": ["DEPTH"],
        "api": ["API_NUMBER"],
        "operator": ["CURR_OPERATOR", "ORIG_OPERATOR"],
        "status": ["STATUS", "STATUS2"],
        "spud_date": ["SPUD"],
    },
)


def _county_from_api(api_str: str) -> str:
    """Extract county name from KS API format: 15-XXX-YYYYY"""
    m = re.match(r"\d{2}-(\d{3})-", api_str or "")
    if m:
        return COUNTY_FIPS.get(m.group(1), "Unknown")
    # Also try raw 14-digit API: 15XXXYYYYY0000
    clean = re.sub(r"[\s\-]", "", api_str or "")
    if len(clean) >= 5:
        return COUNTY_FIPS.get(clean[2:5], "Unknown")
    return "Unknown"


class KSAdapter(DirectDownloadAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        import math
        cfg = self.config

        lat_s = col(row, "LATITUDE")
        lon_s = col(row, "LONGITUDE")
        depth_s = col(row, "DEPTH")
        try:
            lat, lon = float(lat_s), float(lon_s)
            depth = float(depth_s) if depth_s else 0.0
        except (ValueError, TypeError):
            return None

        if not math.isfinite(lat) or not math.isfinite(lon):
            return None
        if depth <= 0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api = col(row, "API_NUMBER")
        operator = col(row, "CURR_OPERATOR") or col(row, "ORIG_OPERATOR") or "Unknown"
        status_raw = col(row, "STATUS") or col(row, "STATUS2")
        status = cfg.resolve_status(status_raw)
        spud = parse_spud_date(col(row, "SPUD"))
        county = _county_from_api(api)

        # Infer well type from initial production flags
        ip_oil = col(row, "IP_OIL")
        ip_gas = col(row, "IP_GAS")
        if ip_oil and ip_gas:
            well_type = "oil-gas"
        elif ip_oil:
            well_type = "oil"
        elif ip_gas:
            well_type = "gas"
        else:
            well_type = "other"

        well = {
            "id": f"ks-{normalize_api(api)}" if api else None,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": int(depth),
            "operator": operator,
            "spud_date": spud,
            "status": status,
            "county": county,
            "state": "KS",
            "source": "ks-kgs",
            "well_type": well_type,
        }
        return self.apply_base_filters(well)


adapter = KSAdapter(_config)
