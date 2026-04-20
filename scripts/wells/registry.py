"""
State registry — maps two-letter state code (or "OFFSHORE") to its Adapter.

Add a new state by:
  1. Creating scripts/wells/states/<abbr>.py with an `adapter` attribute
  2. Importing it here and adding it to REGISTRY
"""

from scripts.wells.states.nd import adapter as nd_adapter
from scripts.wells.states.co import adapter as co_adapter
from scripts.wells.states.offshore import adapter as offshore_adapter
from scripts.wells.states.ks import adapter as ks_adapter
from scripts.wells.states.wy import adapter as wy_adapter
from scripts.wells.states.nm import adapter as nm_adapter
from scripts.wells.states.ca import adapter as ca_adapter
from scripts.wells.states.tx import adapter as tx_adapter
from scripts.wells.states.ok import adapter as ok_adapter
from scripts.wells.states.pa import adapter as pa_adapter
from scripts.wells.states.mt import adapter as mt_adapter
from scripts.wells.states.ut import adapter as ut_adapter
from scripts.wells.states.oh import adapter as oh_adapter
from scripts.wells.states.wv import adapter as wv_adapter
from scripts.wells.states.la import adapter as la_adapter
from scripts.wells.states.il import adapter as il_adapter
from scripts.wells.states.mi import adapter as mi_adapter
from scripts.wells.states.ar import adapter as ar_adapter
from scripts.wells.states.ms import adapter as ms_adapter
from scripts.wells.states.al import adapter as al_adapter
from scripts.wells.states.ak import adapter as ak_adapter
from scripts.wells.states.ny import adapter as ny_adapter
from scripts.wells.states.ky import adapter as ky_adapter

REGISTRY: dict = {
    "ND": nd_adapter,
    "CO": co_adapter,
    "OFFSHORE": offshore_adapter,
    "KS": ks_adapter,
    "WY": wy_adapter,
    "NM": nm_adapter,
    "CA": ca_adapter,
    "TX": tx_adapter,
    "OK": ok_adapter,
    "PA": pa_adapter,
    "MT": mt_adapter,
    "UT": ut_adapter,
    "OH": oh_adapter,
    "WV": wv_adapter,
    "LA": la_adapter,
    "IL": il_adapter,
    "MI": mi_adapter,
    "AR": ar_adapter,
    "MS": ms_adapter,
    "AL": al_adapter,
    "AK": ak_adapter,
    "NY": ny_adapter,
    "KY": ky_adapter,
}
