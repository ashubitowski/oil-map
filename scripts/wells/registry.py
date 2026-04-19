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
}
