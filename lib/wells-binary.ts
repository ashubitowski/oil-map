import type { Well } from "./types";

const MAGIC = "WELL";
const VERSION = 2;

export interface WellDicts {
  operator: string[];
  county: string[];
  status: string[];
  well_type: string[];
  source: string[];
  spud_date: string[];
}

export interface WellColumns {
  count: number;
  state: string;
  lons: Float32Array;
  lats: Float32Array;
  depths: Int32Array;
  operatorIdxs: Uint16Array;
  countyIdxs: Uint16Array;
  statusIdxs: Uint8Array;
  wellTypeIdxs: Uint8Array;
  sourceIdxs: Uint8Array;
  spudDateIdxs: Uint16Array;
  ids: string[];
  dicts: WellDicts;
}

export function decodeWellsBin(buffer: ArrayBuffer): WellColumns {
  const view = new DataView(buffer);

  const magic =
    String.fromCharCode(view.getUint8(0)) +
    String.fromCharCode(view.getUint8(1)) +
    String.fromCharCode(view.getUint8(2)) +
    String.fromCharCode(view.getUint8(3));
  if (magic !== MAGIC) throw new Error(`Invalid binary wells file (magic=${magic})`);

  const version = view.getUint16(4, true);
  if (version !== VERSION) throw new Error(`Unsupported binary wells version: ${version}`);

  const headerLen = view.getUint32(6, true);
  const headerBytes = new Uint8Array(buffer, 10, headerLen);
  const header = JSON.parse(new TextDecoder().decode(headerBytes)) as {
    count: number;
    state: string;
    dicts: WellDicts;
  };

  const { count, state, dicts } = header;

  // Align to 4-byte boundary after the fixed 10-byte prefix + headerLen
  let off = (10 + headerLen + 3) & ~3;

  // Column order matches binary.py: 4-byte → 2-byte → 1-byte (alignment guaranteed)
  const lons         = new Float32Array(buffer, off, count); off += count * 4;
  const lats         = new Float32Array(buffer, off, count); off += count * 4;
  const depths       = new Int32Array  (buffer, off, count); off += count * 4;
  const operatorIdxs = new Uint16Array (buffer, off, count); off += count * 2;
  const countyIdxs   = new Uint16Array (buffer, off, count); off += count * 2;
  const spudDateIdxs = new Uint16Array (buffer, off, count); off += count * 2;
  const idLens       = new Uint16Array (buffer, off, count); off += count * 2;
  const statusIdxs   = new Uint8Array  (buffer, off, count); off += count;
  const wellTypeIdxs = new Uint8Array  (buffer, off, count); off += count;
  const sourceIdxs   = new Uint8Array  (buffer, off, count); off += count;

  const dec = new TextDecoder();
  const ids: string[] = new Array(count);
  for (let i = 0; i < count; i++) {
    const len = idLens[i];
    ids[i] = len > 0 ? dec.decode(new Uint8Array(buffer, off, len)) : "";
    off += len;
  }

  return { count, state, lons, lats, depths, operatorIdxs, countyIdxs, statusIdxs, wellTypeIdxs, sourceIdxs, spudDateIdxs, ids, dicts };
}

export function columnsToWell(c: WellColumns, i: number): Well {
  return {
    id: c.ids[i],
    lat: c.lats[i],
    lon: c.lons[i],
    depth_ft: c.depths[i],
    operator: c.dicts.operator[c.operatorIdxs[i]],
    county: c.dicts.county[c.countyIdxs[i]],
    status: c.dicts.status[c.statusIdxs[i]],
    well_type: c.dicts.well_type[c.wellTypeIdxs[i]] as Well["well_type"],
    source: c.dicts.source[c.sourceIdxs[i]] as Well["source"],
    spud_date: c.dicts.spud_date[c.spudDateIdxs[i]],
    state: c.state,
  };
}

export function findWellIndexById(c: WellColumns, id: string): number {
  return c.ids.indexOf(id);
}

/** Precompute interleaved [lon, lat] Float32Array for deck.gl getPosition binary attribute. */
export function buildPositions(c: WellColumns): Float32Array {
  const out = new Float32Array(c.count * 2);
  for (let i = 0; i < c.count; i++) {
    out[i * 2]     = c.lons[i];
    out[i * 2 + 1] = c.lats[i];
  }
  return out;
}

type Color4 = [number, number, number, number];

function depthToColor(depth_ft: number): Color4 {
  const stops: [number, [number, number, number]][] = [
    [0,     [0,   220, 255]],
    [5000,  [59,  130, 246]],
    [10000, [29,   78, 216]],
    [20000, [15,   23,  42]],
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [d0, c0] = stops[i];
    const [d1, c1] = stops[i + 1];
    if (depth_ft <= d1) {
      const t = (depth_ft - d0) / (d1 - d0);
      return [
        Math.round(c0[0] + t * (c1[0] - c0[0])),
        Math.round(c0[1] + t * (c1[1] - c0[1])),
        Math.round(c0[2] + t * (c1[2] - c0[2])),
        191,
      ];
    }
  }
  return [15, 23, 42, 191];
}

/** Precompute RGBA Uint8Array for deck.gl getFillColor binary attribute.
 *  If `filter` is provided (Uint8Array of 0/1 per well), filtered-out wells get alpha=0. */
export function buildFillColors(c: WellColumns, filter?: Uint8Array): Uint8Array {
  const out = new Uint8Array(c.count * 4);
  for (let i = 0; i < c.count; i++) {
    const [r, g, b, a] = depthToColor(c.depths[i]);
    out[i * 4]     = r;
    out[i * 4 + 1] = g;
    out[i * 4 + 2] = b;
    out[i * 4 + 3] = filter ? (filter[i] ? a : 0) : a;
  }
  return out;
}

/** Build a per-well 0/1 Uint8Array: 1 if well's status is in enabledStatuses, else 0. */
export function buildStatusFilter(c: WellColumns, enabledStatuses: Set<string>): Uint8Array {
  const allowed = c.dicts.status.map((s) => enabledStatuses.has(s) ? 1 : 0);
  const out = new Uint8Array(c.count);
  for (let i = 0; i < c.count; i++) {
    out[i] = allowed[c.statusIdxs[i]];
  }
  return out;
}

/** Count wells per canonical status for the chip badges. */
export function countByStatus(c: WellColumns): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const s of c.dicts.status) counts[s] = 0;
  for (let i = 0; i < c.count; i++) {
    counts[c.dicts.status[c.statusIdxs[i]]]++;
  }
  return counts;
}

const BOEM_SOURCE = "boem";

/** Precompute Float32Array for deck.gl getLineWidth binary attribute. */
export function buildLineWidths(c: WellColumns): Float32Array {
  const boemIdx = c.dicts.source.indexOf(BOEM_SOURCE);
  const out = new Float32Array(c.count);
  for (let i = 0; i < c.count; i++) {
    out[i] = c.sourceIdxs[i] === boemIdx ? 1.5 : 0.5;
  }
  return out;
}

/** Precompute RGBA Uint8Array for deck.gl getLineColor binary attribute. */
export function buildLineColors(c: WellColumns): Uint8Array {
  const boemIdx = c.dicts.source.indexOf(BOEM_SOURCE);
  const out = new Uint8Array(c.count * 4);
  for (let i = 0; i < c.count; i++) {
    const isBoem = c.sourceIdxs[i] === boemIdx;
    out[i * 4]     = isBoem ?   6 : 30;
    out[i * 4 + 1] = isBoem ? 182 : 58;
    out[i * 4 + 2] = isBoem ? 212 : 95;
    out[i * 4 + 3] = isBoem ? 200 : 150;
  }
  return out;
}

export function mergeBinaryColumns(cols: WellColumns[]): WellColumns {
  const total = cols.reduce((s, c) => s + c.count, 0);

  const fields = ["operator", "county", "status", "well_type", "source", "spud_date"] as const;
  const mergedDicts = {} as WellDicts;
  const remaps: Record<string, number[][]> = {};

  for (const field of fields) {
    const seen = new Map<string, number>();
    const unified: string[] = [];
    const colRemaps: number[][] = [];

    for (const col of cols) {
      const dict = col.dicts[field];
      const remap: number[] = new Array(dict.length);
      for (let i = 0; i < dict.length; i++) {
        const v = dict[i];
        if (!seen.has(v)) { seen.set(v, unified.length); unified.push(v); }
        remap[i] = seen.get(v)!;
      }
      colRemaps.push(remap);
    }
    mergedDicts[field] = unified;
    remaps[field] = colRemaps;
  }

  const lons         = new Float32Array(total);
  const lats         = new Float32Array(total);
  const depths       = new Int32Array(total);
  const operatorIdxs = new Uint16Array(total);
  const countyIdxs   = new Uint16Array(total);
  const statusIdxs   = new Uint8Array(total);
  const wellTypeIdxs = new Uint8Array(total);
  const sourceIdxs   = new Uint8Array(total);
  const spudDateIdxs = new Uint16Array(total);
  const ids: string[] = new Array(total);

  let off = 0;
  for (let c = 0; c < cols.length; c++) {
    const col = cols[c];
    const n   = col.count;
    lons.set(col.lons, off);
    lats.set(col.lats, off);
    depths.set(col.depths, off);
    for (let i = 0; i < n; i++) {
      operatorIdxs [off + i] = remaps.operator [c][col.operatorIdxs [i]];
      countyIdxs   [off + i] = remaps.county   [c][col.countyIdxs   [i]];
      statusIdxs   [off + i] = remaps.status   [c][col.statusIdxs   [i]];
      wellTypeIdxs [off + i] = remaps.well_type[c][col.wellTypeIdxs [i]];
      sourceIdxs   [off + i] = remaps.source   [c][col.sourceIdxs   [i]];
      spudDateIdxs [off + i] = remaps.spud_date[c][col.spudDateIdxs [i]];
      ids          [off + i] = col.ids[i];
    }
    off += n;
  }

  return {
    count: total,
    state: cols.map((c) => c.state).join("+"),
    lons, lats, depths,
    operatorIdxs, countyIdxs, statusIdxs, wellTypeIdxs, sourceIdxs, spudDateIdxs,
    ids,
    dicts: mergedDicts,
  };
}
