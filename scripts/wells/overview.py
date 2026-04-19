"""
Generate wells-overview.bin: a 0.25° grid-sampled overview (~10k wells)
for display at map zoom < 6. Keeps the deepest well per grid cell.

Usage: python3 scripts/wells/overview.py
"""
import json
import struct
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.wells.binary import write_wells_bin

GRID_DEG = 0.1
DATA_DIR = _root / "public" / "data"
OUT = DATA_DIR / "wells-overview.bin"


def _read_bin(path: Path) -> list[dict]:
    data = path.read_bytes()
    if data[:4] != b"WELL":
        raise ValueError(f"Not a WELL binary: {path}")
    version = struct.unpack_from("<H", data, 4)[0]
    if version != 2:
        raise ValueError(f"Unsupported version {version} in {path}")
    header_len = struct.unpack_from("<I", data, 6)[0]
    header = json.loads(data[10 : 10 + header_len])
    count = header["count"]
    dicts = header["dicts"]
    state = header.get("state", "")

    prefix = 10 + header_len
    off = prefix + (4 - (prefix % 4)) % 4  # 4-byte align

    lons    = struct.unpack_from(f"<{count}f", data, off); off += count * 4
    lats    = struct.unpack_from(f"<{count}f", data, off); off += count * 4
    depths  = struct.unpack_from(f"<{count}i", data, off); off += count * 4
    op_idx  = struct.unpack_from(f"<{count}H", data, off); off += count * 2
    co_idx  = struct.unpack_from(f"<{count}H", data, off); off += count * 2
    sd_idx  = struct.unpack_from(f"<{count}H", data, off); off += count * 2
    id_lens = struct.unpack_from(f"<{count}H", data, off); off += count * 2
    st_idx  = struct.unpack_from(f"<{count}B", data, off); off += count
    wt_idx  = struct.unpack_from(f"<{count}B", data, off); off += count
    sr_idx  = struct.unpack_from(f"<{count}B", data, off); off += count

    wells = []
    id_off = off
    for i in range(count):
        id_len = id_lens[i]
        wid = data[id_off : id_off + id_len].decode("utf-8")
        id_off += id_len
        wells.append({
            "id": wid,
            "lat": float(lats[i]),
            "lon": float(lons[i]),
            "depth_ft": int(depths[i]),
            "operator": dicts["operator"][op_idx[i]],
            "county": dicts["county"][co_idx[i]],
            "status": dicts["status"][st_idx[i]],
            "well_type": dicts["well_type"][wt_idx[i]],
            "source": dicts["source"][sr_idx[i]],
            "spud_date": dicts["spud_date"][sd_idx[i]],
            "state": state,
        })
    return wells


def main() -> None:
    bin_files = sorted(f for f in DATA_DIR.glob("wells-*.bin") if "overview" not in f.name)
    if not bin_files:
        print(f"No wells-*.bin files found in {DATA_DIR}")
        sys.exit(1)

    # (cell_x, cell_y) → deepest well in that cell
    grid: dict[tuple[int, int], dict] = {}

    for path in bin_files:
        print(f"  Reading {path.name}...", flush=True)
        wells = _read_bin(path)
        before = len(grid)
        for w in wells:
            cx = int(w["lon"] / GRID_DEG)
            cy = int(w["lat"] / GRID_DEG)
            key = (cx, cy)
            if key not in grid or w["depth_ft"] > grid[key]["depth_ft"]:
                grid[key] = w
        print(f"    {len(wells):,} wells → {len(grid) - before:+,} new cells (total {len(grid):,})")

    sampled = list(grid.values())
    print(f"\nSampling done: {len(sampled):,} overview wells from {len(bin_files)} state file(s)")

    write_wells_bin(sampled, OUT)
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
