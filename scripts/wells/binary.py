"""
Binary columnar format writer for well data.

Layout (little-endian throughout):
  [4 bytes]  magic = b"WELL"
  [2 bytes]  version = 2 (uint16)
  [4 bytes]  header_len (uint32) — byte length of header JSON (unpadded)
  [N bytes]  header JSON (UTF-8)
  [P bytes]  padding to align next section to 4-byte boundary
  --- fixed-width columns (each column is `count` elements) ---
  Float32[count]  lons
  Float32[count]  lats
  Int32[count]    depth_ft
  Uint16[count]   operator_idx
  Uint16[count]   county_idx
  Uint8[count]    status_idx
  Uint8[count]    well_type_idx
  Uint8[count]    source_idx
  Uint16[count]   spud_date_idx
  Uint16[count]   id_len           (byte length of each UTF-8 id string)
  --- variable section ---
  [all id bytes concatenated, in row order]
"""

import gzip
import json
import struct
from pathlib import Path

MAGIC = b"WELL"
VERSION = 2


def _make_dict(values):
    """Return (list_of_uniques, {value: index}) preserving insertion order."""
    seen: dict = {}
    for v in values:
        if v not in seen:
            seen[v] = len(seen)
    return list(seen.keys()), seen


def write_wells_bin(wells: list, path: Path) -> None:
    n = len(wells)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Determine the single state for this file (all rows share one state)
    state = wells[0].get("state", "") if wells else ""

    # Build dicts
    operator_list, op_idx = _make_dict(w.get("operator") or "Unknown" for w in wells)
    county_list, co_idx  = _make_dict(w.get("county")   or "Unknown" for w in wells)
    status_list, st_idx  = _make_dict(w.get("status")   or "Unknown" for w in wells)
    wt_list,     wt_idx  = _make_dict(w.get("well_type")or "other"   for w in wells)
    src_list,    sr_idx  = _make_dict(w.get("source")   or ""        for w in wells)
    sd_list,     sd_idx  = _make_dict(w.get("spud_date")or ""        for w in wells)

    # Guard index sizes
    if len(operator_list) > 65535:
        raise ValueError(f"Too many unique operators ({len(operator_list)}) for Uint16")
    if len(county_list) > 65535:
        raise ValueError(f"Too many unique counties ({len(county_list)}) for Uint16")
    if len(sd_list) > 65535:
        raise ValueError(f"Too many unique spud dates ({len(sd_list)}) for Uint16")
    if len(status_list) > 255 or len(wt_list) > 255 or len(src_list) > 255:
        raise ValueError("Status/well_type/source dict exceeds Uint8 capacity")

    header = {
        "count": n,
        "state": state,
        "dicts": {
            "operator":  operator_list,
            "county":    county_list,
            "status":    status_list,
            "well_type": wt_list,
            "source":    src_list,
            "spud_date": sd_list,
        },
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")

    # ID bytes (UTF-8, variable length)
    id_byte_list = [(w.get("id") or "").encode("utf-8") for w in wells]
    id_lens_list = [len(b) for b in id_byte_list]
    id_data = b"".join(id_byte_list)

    # Precompute index sequences
    # Column order: 4-byte → 2-byte → 1-byte so TypedArray views are always aligned
    lons_data   = struct.pack(f"<{n}f", *(float(w["lon"])        for w in wells))
    lats_data   = struct.pack(f"<{n}f", *(float(w["lat"])        for w in wells))
    depths_data = struct.pack(f"<{n}i", *(int(w["depth_ft"])     for w in wells))
    op_data     = struct.pack(f"<{n}H", *(op_idx[w.get("operator")  or "Unknown"] for w in wells))
    co_data     = struct.pack(f"<{n}H", *(co_idx[w.get("county")    or "Unknown"] for w in wells))
    sd_data     = struct.pack(f"<{n}H", *(sd_idx[w.get("spud_date") or ""       ] for w in wells))
    id_len_data = struct.pack(f"<{n}H", *id_lens_list)
    st_data     = struct.pack(f"<{n}B", *(st_idx[w.get("status")    or "Unknown"] for w in wells))
    wt_data     = struct.pack(f"<{n}B", *(wt_idx[w.get("well_type") or "other"  ] for w in wells))
    sr_data     = struct.pack(f"<{n}B", *(sr_idx[w.get("source")    or ""       ] for w in wells))

    # Padding after header so columns start at 4-byte boundary
    # Fixed prefix size: 4 (magic) + 2 (version) + 4 (header_len) = 10 bytes
    prefix_size = 10 + len(header_bytes)
    pad = (4 - (prefix_size % 4)) % 4

    bin_bytes = (
        MAGIC
        + struct.pack("<H", VERSION)
        + struct.pack("<I", len(header_bytes))
        + header_bytes
        + (b"\x00" * pad)
        + lons_data + lats_data + depths_data
        + op_data + co_data + sd_data + id_len_data
        + st_data + wt_data + sr_data
        + id_data
    )

    with open(path, "wb") as f:
        f.write(bin_bytes)

    gz_path = path.with_suffix(path.suffix + ".gz")
    with open(gz_path, "wb") as f:
        f.write(gzip.compress(bin_bytes, compresslevel=9))
