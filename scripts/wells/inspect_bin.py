"""
Debugging tool: decode a wells .bin file and print rows as JSON.

Usage:
  python3 scripts/wells/inspect_bin.py public/data/wells-nd.bin
  python3 scripts/wells/inspect_bin.py public/data/wells-nd.bin --rows 5
  python3 scripts/wells/inspect_bin.py public/data/wells-nd.bin --header
"""

import json
import struct
import sys
from pathlib import Path

MAGIC = b"WELL"
VERSION = 2


def decode(path: Path, max_rows=10, header_only: bool = False) -> None:
    data = path.read_bytes()
    if data[:4] != MAGIC:
        raise ValueError(f"Not a WELL binary file (got {data[:4]!r})")

    version = struct.unpack_from("<H", data, 4)[0]
    if version != VERSION:
        raise ValueError(f"Unsupported version {version}")

    header_len = struct.unpack_from("<I", data, 6)[0]
    header = json.loads(data[10 : 10 + header_len])
    count = header["count"]
    dicts = header["dicts"]

    print(f"File:    {path}")
    print(f"Version: {version}")
    print(f"State:   {header.get('state', '?')}")
    print(f"Count:   {count:,} wells")
    print(f"Dicts:   operator={len(dicts['operator'])}, county={len(dicts['county'])},",
          f"status={len(dicts['status'])}, well_type={len(dicts['well_type'])},",
          f"source={len(dicts['source'])}, spud_date={len(dicts['spud_date'])}")
    print(f"Size:    {path.stat().st_size / 1e6:.2f} MB")

    if header_only:
        return

    # Locate column data
    prefix = 10 + header_len
    col_off = prefix + (4 - (prefix % 4)) % 4  # align to 4 bytes

    def read_f32(offset, n):
        return struct.unpack_from(f"<{n}f", data, offset), offset + n * 4

    def read_i32(offset, n):
        return struct.unpack_from(f"<{n}i", data, offset), offset + n * 4

    def read_u16(offset, n):
        return struct.unpack_from(f"<{n}H", data, offset), offset + n * 4 // 2 * 2  # keep aligned

    def read_u8(offset, n):
        return struct.unpack_from(f"<{n}B", data, offset), offset + n

    off = col_off
    lons,    off = struct.unpack_from(f"<{count}f", data, off), off + count * 4
    lats,    off = struct.unpack_from(f"<{count}f", data, off), off + count * 4
    depths,  off = struct.unpack_from(f"<{count}i", data, off), off + count * 4
    op_idx,  off = struct.unpack_from(f"<{count}H", data, off), off + count * 2
    co_idx,  off = struct.unpack_from(f"<{count}H", data, off), off + count * 2
    sd_idx,  off = struct.unpack_from(f"<{count}H", data, off), off + count * 2
    id_lens, off = struct.unpack_from(f"<{count}H", data, off), off + count * 2
    st_idx,  off = struct.unpack_from(f"<{count}B", data, off), off + count
    wt_idx,  off = struct.unpack_from(f"<{count}B", data, off), off + count
    sr_idx,  off = struct.unpack_from(f"<{count}B", data, off), off + count

    print()

    limit = count if max_rows is None else min(max_rows, count)
    id_off = off
    for i in range(limit):
        id_len = id_lens[i]
        well_id = data[id_off : id_off + id_len].decode("utf-8")
        id_off += id_len
        row = {
            "id": well_id,
            "lat": round(lats[i], 6),
            "lon": round(lons[i], 6),
            "depth_ft": depths[i],
            "operator": dicts["operator"][op_idx[i]],
            "county": dicts["county"][co_idx[i]],
            "status": dicts["status"][st_idx[i]],
            "well_type": dicts["well_type"][wt_idx[i]],
            "source": dicts["source"][sr_idx[i]],
            "spud_date": dicts["spud_date"][sd_idx[i]],
        }
        print(json.dumps(row))


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    path = Path(args[0])
    header_only = "--header" in args
    rows = 10
    if "--rows" in args:
        idx = args.index("--rows")
        rows = int(args[idx + 1])

    decode(path, max_rows=None if "--all" in args else rows, header_only=header_only)


if __name__ == "__main__":
    main()
