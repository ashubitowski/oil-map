"""
Texas — TxDOT/RRC Statewide Surface Wells (ArcGIS mirror)

Source: TxDOT-hosted AGOL FeatureServer mirroring RRC well locations
  https://services.arcgis.com/KTcxiTD9dsQw4r7Z/ArcGIS/rest/services/
    Statewide_Surface_Wells_Aug2019/FeatureServer/0
  ~1.33M surface well locations, WGS84 geometry, 8-digit API.

Available attributes: lat (LAT83), lon (LONG83), API, SYMNUM (type/status).
Depth, operator, and spud_date are not available from this public endpoint
(RRC bulk attribute dumps require portal authentication). Those fields will
be populated as "Unknown"/"" and depth_ft=0.

County is derived from the first 3 digits of the API number, which encode
the Texas FIPS county code in the RRC numbering scheme.

SYMNUM codes (RRC oil/gas well symbology):
  1 = Oil well - Active      2 = Gas well - Active
  3 = Oil well - P&A         4 = Gas well - P&A
  5 = Oil well - Active (alt class)   6 = Gas well - Active (alt)
  7 = Injection - Active     8 = Injection - P&A
  9 = Disposal - Active     10 = Other/Unknown
  11-19 = Well service types        20+ = Compound/special codes
"""

from pathlib import Path

from scripts.wells.adapters.arcgis_rest import ArcGISAdapter
from scripts.wells.adapters.base import BaseConfig
from scripts.wells.schema import is_in_bounds

AGOL_URL = (
    "https://services.arcgis.com/KTcxiTD9dsQw4r7Z/ArcGIS/rest/services/"
    "Statewide_Surface_Wells_Aug2019/FeatureServer/0"
)

# Texas FIPS county codes → county name (254 counties)
_TX_COUNTIES: dict[str, str] = {
    "001": "Anderson", "003": "Andrews", "005": "Angelina", "007": "Aransas",
    "009": "Archer", "011": "Armstrong", "013": "Atascosa", "015": "Austin",
    "017": "Bailey", "019": "Bandera", "021": "Bastrop", "023": "Baylor",
    "025": "Bee", "027": "Bell", "029": "Bexar", "031": "Blanco",
    "033": "Borden", "035": "Bosque", "037": "Bowie", "039": "Brazoria",
    "041": "Brazos", "043": "Brewster", "045": "Briscoe", "047": "Brooks",
    "049": "Brown", "051": "Burleson", "053": "Burnet", "055": "Caldwell",
    "057": "Calhoun", "059": "Callahan", "061": "Cameron", "063": "Camp",
    "065": "Carson", "067": "Cass", "069": "Castro", "071": "Chambers",
    "073": "Cherokee", "075": "Childress", "077": "Clay", "079": "Cochran",
    "081": "Coke", "083": "Coleman", "085": "Collin", "087": "Collingsworth",
    "089": "Colorado", "091": "Comal", "093": "Comanche", "095": "Concho",
    "097": "Cooke", "099": "Coryell", "101": "Cottle", "103": "Crane",
    "105": "Crockett", "107": "Crosby", "109": "Culberson", "111": "Dallam",
    "113": "Dallas", "115": "Dawson", "117": "Deaf Smith", "119": "Delta",
    "121": "Denton", "123": "DeWitt", "125": "Dickens", "127": "Dimmit",
    "129": "Donley", "131": "Duval", "133": "Eastland", "135": "Ector",
    "137": "Edwards", "139": "Ellis", "141": "El Paso", "143": "Erath",
    "145": "Falls", "147": "Fannin", "149": "Fayette", "151": "Fisher",
    "153": "Floyd", "155": "Foard", "157": "Fort Bend", "159": "Franklin",
    "161": "Freestone", "163": "Frio", "165": "Gaines", "167": "Galveston",
    "169": "Garza", "171": "Gillespie", "173": "Glasscock", "175": "Goliad",
    "177": "Gonzales", "179": "Gray", "181": "Grayson", "183": "Gregg",
    "185": "Grimes", "187": "Guadalupe", "189": "Hale", "191": "Hall",
    "193": "Hamilton", "195": "Hansford", "197": "Hardeman", "199": "Hardin",
    "201": "Harris", "203": "Harrison", "205": "Hartley", "207": "Haskell",
    "209": "Hays", "211": "Hemphill", "213": "Henderson", "215": "Hidalgo",
    "217": "Hill", "219": "Hockley", "221": "Hood", "223": "Hopkins",
    "225": "Houston", "227": "Howard", "229": "Hudspeth", "231": "Hunt",
    "233": "Hutchinson", "235": "Irion", "237": "Jack", "239": "Jackson",
    "241": "Jasper", "243": "Jeff Davis", "245": "Jefferson", "247": "Jim Hogg",
    "249": "Jim Wells", "251": "Johnson", "253": "Jones", "255": "Karnes",
    "257": "Kaufman", "259": "Kendall", "261": "Kenedy", "263": "Kent",
    "265": "Kerr", "267": "Kimble", "269": "King", "271": "Kinney",
    "273": "Kleberg", "275": "Knox", "277": "Lamar", "279": "Lamb",
    "281": "Lampasas", "283": "La Salle", "285": "Lavaca", "287": "Lee",
    "289": "Leon", "291": "Liberty", "293": "Limestone", "295": "Lipscomb",
    "297": "Live Oak", "299": "Llano", "301": "Loving", "303": "Lubbock",
    "305": "Lynn", "307": "McCulloch", "309": "McLennan", "311": "McMullen",
    "313": "Madison", "315": "Marion", "317": "Martin", "319": "Mason",
    "321": "Matagorda", "323": "Maverick", "325": "Medina", "327": "Menard",
    "329": "Midland", "331": "Milam", "333": "Mills", "335": "Mitchell",
    "337": "Montague", "339": "Montgomery", "341": "Moore", "343": "Morris",
    "345": "Motley", "347": "Nacogdoches", "349": "Navarro", "351": "Newton",
    "353": "Nolan", "355": "Nueces", "357": "Ochiltree", "359": "Oldham",
    "361": "Orange", "363": "Palo Pinto", "365": "Panola", "367": "Parker",
    "369": "Parmer", "371": "Pecos", "373": "Polk", "375": "Potter",
    "377": "Presidio", "379": "Rains", "381": "Randall", "383": "Reagan",
    "385": "Real", "387": "Red River", "389": "Reeves", "391": "Refugio",
    "393": "Roberts", "395": "Robertson", "397": "Rockwall", "399": "Runnels",
    "401": "Rusk", "403": "Sabine", "405": "San Augustine", "407": "San Jacinto",
    "409": "San Patricio", "411": "San Saba", "413": "Schleicher", "415": "Scurry",
    "417": "Shackelford", "419": "Shelby", "421": "Sherman", "423": "Smith",
    "425": "Somervell", "427": "Starr", "429": "Stephens", "431": "Sterling",
    "433": "Stonewall", "435": "Sutton", "437": "Swisher", "439": "Tarrant",
    "441": "Taylor", "443": "Terrell", "445": "Terry", "447": "Throckmorton",
    "449": "Titus", "451": "Tom Green", "453": "Travis", "455": "Trinity",
    "457": "Tyler", "459": "Upshur", "461": "Upton", "463": "Uvalde",
    "465": "Val Verde", "467": "Van Zandt", "469": "Victoria", "471": "Walker",
    "473": "Waller", "475": "Ward", "477": "Washington", "479": "Webb",
    "481": "Wharton", "483": "Wheeler", "485": "Wichita", "487": "Wilbarger",
    "489": "Willacy", "491": "Williamson", "493": "Wilson", "495": "Winkler",
    "497": "Wise", "499": "Wood", "501": "Yoakum", "503": "Young",
    "505": "Zapata", "507": "Zavala",
}

# SYMNUM → (well_type, status) — approximate, based on RRC GIS symbology
_SYMNUM_MAP: dict[int, tuple[str, str]] = {
    1:  ("oil",       "Active"),
    2:  ("gas",       "Active"),
    3:  ("oil",       "Plugged & Abandoned"),
    4:  ("gas",       "Plugged & Abandoned"),
    5:  ("oil",       "Active"),
    6:  ("gas",       "Active"),
    7:  ("injection", "Active"),
    8:  ("injection", "Plugged & Abandoned"),
    9:  ("disposal",  "Active"),
    10: ("other",     "Inactive"),
    11: ("other",     "Active"),
    12: ("other",     "Plugged & Abandoned"),
}

_config = BaseConfig(
    state="TX",
    source_label="rrc",
    url=AGOL_URL,
    bounds=(25.8, 36.5, -106.7, -93.5),
    output=Path("public/data/wells-tx.json"),
    raw_dir=Path("data/raw/tx"),
    require_depth=False,   # depth not available from this source
    field_map={
        "lat": ["_lat", "LAT83"],
        "lon": ["_lon", "LONG83"],
        "api": ["API", "WELLID"],
    },
)


class TXAdapter(ArcGISAdapter):
    def normalize_row(self, row: dict) -> "dict | None":
        cfg = self.config

        try:
            lat = float(row.get("_lat") or row.get("LAT83") or 0)
            lon = float(row.get("_lon") or row.get("LONG83") or 0)
        except (TypeError, ValueError):
            return None
        if lat == 0.0 or lon == 0.0:
            return None
        if not is_in_bounds(lat, lon, cfg.bounds):
            return None

        api_raw = str(row.get("API") or row.get("WELLID") or "").strip().zfill(8)
        county_code = api_raw[:3].zfill(3) if api_raw else "000"
        county = _TX_COUNTIES.get(county_code, "Unknown")

        # Full 10-digit API: TX state code (42) + 8-char AGOL API
        api_full = "42" + api_raw if api_raw else ""
        well_id = f"tx-{api_full}" if api_full else None

        symnum = int(row.get("SYMNUM") or 0)
        well_type, status = _SYMNUM_MAP.get(symnum, ("other", "Unknown"))

        return {
            "id": well_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "depth_ft": 0,         # not available from this source
            "operator": "Unknown",
            "spud_date": "",
            "status": status,
            "county": county,
            "state": "TX",
            "source": "rrc",
            "well_type": well_type,
        }


adapter = TXAdapter(_config)
