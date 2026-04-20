"""
Illinois — ISGS Oil & Gas Wells (ArcGIS MapServer)

Source: Illinois State Geological Survey (ISGS) ArcGIS MapServer
  https://maps.isgs.illinois.edu/arcgis/rest/services/ILOIL/Wells/MapServer/8
  ~207k wells.

Fields used:
  LATITUDE / LONGITUDE   — surface coords (WGS84 attributes)
  TOTAL_DEPTH            — depth (ft)
  COMPANY_NAME           — operator
  COMP_DATE              — completion date (epoch ms)
  STATUS                 — status code
  API_NUMBER             — 12-digit API; digits [2:5] encode county (IL FIPS)
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import normalize_api, is_in_bounds

_URL = "https://maps.isgs.illinois.edu/arcgis/rest/services/ILOIL/Wells/MapServer/8"

# Illinois county FIPS codes → county name
_IL_COUNTIES: dict[str, str] = {
    "001": "Adams",       "003": "Alexander",  "005": "Bond",
    "007": "Boone",       "009": "Brown",      "011": "Bureau",
    "013": "Calhoun",     "015": "Carroll",    "017": "Cass",
    "019": "Champaign",   "021": "Christian",  "023": "Clark",
    "025": "Clay",        "027": "Clinton",    "029": "Coles",
    "031": "Cook",        "033": "Crawford",   "035": "Cumberland",
    "037": "DeKalb",      "039": "De Witt",    "041": "Douglas",
    "043": "DuPage",      "045": "Edgar",      "047": "Edwards",
    "049": "Effingham",   "051": "Fayette",    "053": "Ford",
    "055": "Franklin",    "057": "Fulton",     "059": "Gallatin",
    "061": "Greene",      "063": "Grundy",     "065": "Hamilton",
    "067": "Hancock",     "069": "Hardin",     "071": "Henderson",
    "073": "Henry",       "075": "Iroquois",   "077": "Jackson",
    "079": "Jasper",      "081": "Jefferson",  "083": "Jersey",
    "085": "Jo Daviess",  "087": "Johnson",    "089": "Kane",
    "091": "Kankakee",    "093": "Kendall",    "095": "Knox",
    "097": "Lake",        "099": "LaSalle",    "101": "Lawrence",
    "103": "Lee",         "105": "Livingston", "107": "Logan",
    "109": "McDonough",   "111": "McHenry",    "113": "McLean",
    "115": "Macon",       "117": "Macoupin",   "119": "Madison",
    "121": "Marion",      "123": "Marshall",   "125": "Mason",
    "127": "Massac",      "129": "Menard",     "131": "Mercer",
    "133": "Monroe",      "135": "Montgomery", "137": "Morgan",
    "139": "Moultrie",    "141": "Ogle",       "143": "Peoria",
    "145": "Perry",       "147": "Piatt",      "149": "Pike",
    "151": "Pope",        "153": "Pulaski",    "155": "Putnam",
    "157": "Randolph",    "159": "Richland",   "161": "Rock Island",
    "163": "St. Clair",   "165": "Saline",     "167": "Sangamon",
    "169": "Schuyler",    "171": "Scott",      "173": "Shelby",
    "175": "Stark",       "177": "Stephenson", "179": "Tazewell",
    "181": "Union",       "183": "Vermilion",  "185": "Wabash",
    "187": "Warren",      "189": "Washington", "191": "Wayne",
    "193": "White",       "195": "Whiteside",  "197": "Will",
    "199": "Williamson",  "201": "Winnebago",  "203": "Woodford",
}

_config = BaseConfig(
    state="IL",
    source_label="il-isgs",
    url=_URL,
    bounds=(36.9, 42.6, -91.6, -87.0),
    output=Path("public/data/wells-il.json"),
    raw_dir=Path("data/raw/il"),
    require_depth=False,
    status_map={
        # Active producers
        "OIL":     "Active",
        "GAS":     "Active",
        "OILGS":   "Active",    # combination oil+gas
        "CBM":     "Active",    # coal bed methane
        "CMM":     "Active",    # coal mine methane
        # Injection / service wells (active)
        "INJW":    "Active",
        "INJG":    "Active",
        "INJ":     "Active",
        "INJSW":   "Active",
        "SWD":     "Active",
        "INJCM":   "Active",
        "INJA":    "Active",
        "INJWS":   "Active",
        "INJT":    "Active",
        "INJD":    "Active",
        "INJCS":   "Active",
        "INJWOG":  "Active",
        "INJWO":   "Active",
        "OILWI":   "Active",
        "OILSD":   "Active",
        "WASTE":   "Active",
        "GSTG":    "Active",    # gas storage
        "OBS":     "Active",    # observation
        "OBSO":    "Active",
        "OBSG":    "Active",
        "OBSOG":   "Active",
        "WATRS":   "Active",    # water supply
        "METHV":   "Active",    # methane vent
        "CPROT":   "Active",    # corrosion protection
        "ENG":     "Active",    # engineering test
        # Temporarily abandoned → Inactive
        "TA":      "Inactive",
        "TAO":     "Inactive",
        "TAG":     "Inactive",
        "TAOG":    "Inactive",
        # Permitted
        "PERMIT":  "Permitted",
        # Plugged & Abandoned (suffix P = plugged)
        "OILP":    "Plugged & Abandoned",
        "GASP":    "Plugged & Abandoned",
        "OILGSP":  "Plugged & Abandoned",
        "CBMP":    "Plugged & Abandoned",
        "CMMP":    "Plugged & Abandoned",
        "DAP":     "Plugged & Abandoned",
        "DAOP":    "Plugged & Abandoned",
        "DAGP":    "Plugged & Abandoned",
        "DAOGP":   "Plugged & Abandoned",
        "DA":      "Plugged & Abandoned",
        "DAO":     "Plugged & Abandoned",
        "DAG":     "Plugged & Abandoned",
        "DAOG":    "Plugged & Abandoned",
        "DAW":     "Plugged & Abandoned",
        "DAWP":    "Plugged & Abandoned",
        "DAX":     "Plugged & Abandoned",
        "JAP":     "Plugged & Abandoned",
        "JA":      "Plugged & Abandoned",
        "JAO":     "Plugged & Abandoned",
        "JAG":     "Plugged & Abandoned",
        "JAOP":    "Plugged & Abandoned",
        "JAOGP":   "Plugged & Abandoned",
        "TAP":     "Plugged & Abandoned",
        "TAOP":    "Plugged & Abandoned",
        "TAGP":    "Plugged & Abandoned",
        "TAOGP":   "Plugged & Abandoned",
        "TAX":     "Plugged & Abandoned",
        "INJWP":   "Plugged & Abandoned",
        "INJGP":   "Plugged & Abandoned",
        "INJP":    "Plugged & Abandoned",
        "INJSWP":  "Plugged & Abandoned",
        "INJCMP":  "Plugged & Abandoned",
        "INJAP":   "Plugged & Abandoned",
        "INJWOP":  "Plugged & Abandoned",
        "INJWSP":  "Plugged & Abandoned",
        "INJCSP":  "Plugged & Abandoned",
        "INJSP":   "Plugged & Abandoned",
        "INJX":    "Plugged & Abandoned",
        "SWDP":    "Plugged & Abandoned",
        "GSTGP":   "Plugged & Abandoned",
        "OBSP":    "Plugged & Abandoned",
        "OBSOP":   "Plugged & Abandoned",
        "WATRSP":  "Plugged & Abandoned",
        "STRATP":  "Plugged & Abandoned",
        "STRUP":   "Plugged & Abandoned",
        "PLUG":    "Plugged & Abandoned",
        "OILX":    "Plugged & Abandoned",
        "GASX":    "Plugged & Abandoned",
        "OILWIP":  "Plugged & Abandoned",
        "OILSDP":  "Plugged & Abandoned",
        "WASTEP":  "Plugged & Abandoned",
        "METHVP":  "Plugged & Abandoned",
        "CPROTP":  "Plugged & Abandoned",
        # Unknown / confidential / misc
        "UNK":     "Unknown",
        "UNKP":    "Unknown",
        "CONF":    "Unknown",
        "STRAT":   "Unknown",
        "STRU":    "Unknown",
        "ABLOC":   "Unknown",
        "DEAD":    "Unknown",
        "OILW":    "Unknown",
        "SALTO":   "Unknown",
        "DRY":     "Unknown",
    },
    well_type_map={
        "OIL":     "oil",
        "OILP":    "oil",
        "OILX":    "oil",
        "OILW":    "oil",
        "OILGS":   "oil-gas",
        "OILGSP":  "oil-gas",
        "GAS":     "gas",
        "GASP":    "gas",
        "GASX":    "gas",
        "GSTG":    "gas",
        "GSTGP":   "gas",
        "CBM":     "gas",
        "CBMP":    "gas",
        "CMM":     "gas",
        "CMMP":    "gas",
        "METHV":   "gas",
        "METHVP":  "gas",
        "INJW":    "injection",
        "INJWP":   "injection",
        "INJG":    "injection",
        "INJGP":   "injection",
        "INJ":     "injection",
        "INJP":    "injection",
        "INJX":    "injection",
        "INJSW":   "injection",
        "INJSWP":  "injection",
        "SWD":     "disposal",
        "SWDP":    "disposal",
        "OILWI":   "injection",
        "OILWIP":  "injection",
        "OILSD":   "disposal",
        "OILSDP":  "disposal",
        "INJCM":   "injection",
        "INJCMP":  "injection",
        "INJA":    "injection",
        "INJAP":   "injection",
        "INJWS":   "injection",
        "INJWSP":  "injection",
        "INJT":    "injection",
        "INJD":    "injection",
        "INJCS":   "injection",
        "INJCSP":  "injection",
        "INJWOG":  "injection",
        "INJWO":   "injection",
        "INJWOP":  "injection",
        "INJSP":   "injection",
        "WASTE":   "disposal",
        "WASTEP":  "disposal",
        "WATRS":   "other",
        "WATRSP":  "other",
        "OBS":     "other",
        "OBSP":    "other",
        "OBSO":    "other",
        "OBSOP":   "other",
        "OBSG":    "other",
        "OBSOG":   "other",
        "CPROT":   "other",
        "CPROTP":  "other",
        "ENG":     "other",
        "STRAT":   "other",
        "STRATP":  "other",
        "STRU":    "other",
        "STRUP":   "other",
        "PLUG":    "other",
        "SALTO":   "other",
        "DRY":     "other",
        "ABLOC":   "other",
        "DEAD":    "other",
        "DA":      "other",
        "DAP":     "other",
        "DAO":     "other",
        "DAOP":    "other",
        "DAG":     "other",
        "DAGP":    "other",
        "DAOG":    "other",
        "DAOGP":   "other",
        "DAW":     "other",
        "DAWP":    "other",
        "DAX":     "other",
        "JA":      "other",
        "JAP":     "other",
        "JAO":     "other",
        "JAG":     "other",
        "JAOP":    "other",
        "JAOGP":   "other",
        "TA":      "other",
        "TAP":     "other",
        "TAO":     "other",
        "TAOP":    "other",
        "TAG":     "other",
        "TAGP":    "other",
        "TAOG":    "other",
        "TAOGP":   "other",
        "TAX":     "other",
        "UNK":     "other",
        "UNKP":    "other",
        "CONF":    "other",
        "PERMIT":  "other",
        "OILX":    "oil",
        "GASX":    "gas",
    },
    field_map={
        "lat":       ["LATITUDE", "_lat"],
        "lon":       ["LONGITUDE", "_lon"],
        "depth_ft":  ["TOTAL_DEPTH"],
        "operator":  ["COMPANY_NAME"],
        "status":    ["STATUS"],
        "well_type": ["STATUS"],
        "api":       ["API_NUMBER"],
    },
)


class ILAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> Optional[dict]:
        cfg = self.config

        try:
            lat = float(row.get("LATITUDE") or row.get("_lat") or 0)
            lon = float(row.get("LONGITUDE") or row.get("_lon") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API_NUMBER") or "").strip()
        if not api_raw:
            return None

        # Derive county from API number digits [2:5] (IL FIPS county code)
        county = "Unknown"
        if len(api_raw) >= 5:
            county_code = api_raw[2:5]
            county = _IL_COUNTIES.get(county_code, "Unknown")

        depth_raw = row.get("TOTAL_DEPTH")
        try:
            depth_ft = int(depth_raw) if depth_raw else 0
        except (TypeError, ValueError):
            depth_ft = 0
        if depth_ft > 40000:
            depth_ft = 0

        # COMP_DATE is epoch milliseconds
        comp_ms = row.get("COMP_DATE")
        spud_date = ""
        if comp_ms:
            try:
                dt = datetime.fromtimestamp(int(comp_ms) / 1000, tz=timezone.utc)
                # Sanity check: ISGS has wells back to early 1900s
                if dt.year >= 1850:
                    spud_date = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                pass

        status_code = str(row.get("STATUS") or "").strip().upper()
        status = cfg.resolve_status(status_code)
        well_type = cfg.resolve_well_type(status_code)
        operator = str(row.get("COMPANY_NAME") or "Unknown").strip() or "Unknown"

        return {
            "id": f"il-{normalize_api(api_raw)}",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": depth_ft,
            "operator": operator,
            "spud_date": spud_date,
            "status": status,
            "county": county,
            "state": "IL",
            "source": "il-isgs",
            "well_type": well_type,
        }


adapter = ILAdapter(_config)
