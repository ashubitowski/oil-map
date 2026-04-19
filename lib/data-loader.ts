import type { WellColumns, WellDicts } from "./wells-binary";

const cache: Record<string, unknown> = {};

// When NEXT_PUBLIC_DATA_BASE_URL is set (e.g., an R2 bucket URL like
// "https://data.example.com/data"), all /data/* fetches are redirected there.
// Leave it unset for local dev — requests fall through to public/data/*.
const DATA_BASE = process.env.NEXT_PUBLIC_DATA_BASE_URL ?? "";
const VERCEL_ONLY = ["/data/production-history.json", "/data/production-basins.json"];
function resolveDataPath(p: string): string {
  if (!DATA_BASE || VERCEL_ONLY.includes(p)) return p;
  return p.replace(/^\/data/, DATA_BASE);
}

export async function loadGeoJSON(path: string) {
  if (cache[path]) return cache[path];
  const res = await fetch(resolveDataPath(path));
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  const data = await res.json();
  cache[path] = data;
  return data;
}

export async function loadJSON<T>(path: string): Promise<T> {
  if (cache[path]) return cache[path] as T;
  const res = await fetch(resolveDataPath(path));
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  const data = await res.json();
  cache[path] = data;
  return data;
}

/** Fetch a bin file, trying `.gz` first (decompressed on caller's side). */
export async function loadBin(path: string): Promise<ArrayBuffer> {
  const gzRes = await fetch(resolveDataPath(path) + ".gz");
  if (gzRes.ok) {
    const compressed = await gzRes.arrayBuffer();
    return new Response(
      new Blob([compressed]).stream().pipeThrough(new DecompressionStream("gzip"))
    ).arrayBuffer();
  }
  const res = await fetch(resolveDataPath(path));
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.arrayBuffer();
}

export interface PrebuiltAttrs {
  positions: Float32Array;
  lineWidths: Float32Array;
  lineColors: Uint8Array;
  fillColors: Uint8Array;
  elevations: Float32Array;
  depthColors: Uint8Array;
  filteredCount: number;
  filterKey: string;
  rawCounts: Record<string, number>;
}

/** Fetch a .bin state file and decode it on a Web Worker.
 *  Returns WellColumns (typed-array views into the transferred buffer)
 *  plus prebuilt stable attributes (positions, lineWidths, lineColors, elevations, depthColors, rawCounts). */
export async function loadWellsState(
  _stateKey: string,
  url: string
): Promise<{ cols: WellColumns; attrs: PrebuiltAttrs }> {
  // Try compressed first; fall back to plain .bin
  let buffer: ArrayBuffer;
  let compressed = false;
  const resolvedUrl = resolveDataPath(url);
  const gzRes = await fetch(resolvedUrl + ".gz");
  if (gzRes.ok) {
    buffer = await gzRes.arrayBuffer();
    compressed = true;
  } else {
    const res = await fetch(resolvedUrl);
    if (!res.ok) throw new Error(`Failed to load ${url}: ${res.status}`);
    buffer = await res.arrayBuffer();
  }

  return new Promise((resolve, reject) => {
    const worker = new Worker(
      new URL("./wells-worker.ts", import.meta.url),
      { type: "module" }
    );

    worker.onmessage = (e) => {
      worker.terminate();
      const m = e.data;

      // Reconstruct typed-array views over the returned buffer (zero-copy on both ends)
      const cols: WellColumns = {
        count: m.count,
        state: m.state,
        ids:   m.ids,
        dicts: m.dicts as WellDicts,
        lons:         new Float32Array(m.buffer, m.lonsOff,         m.lonsLen),
        lats:         new Float32Array(m.buffer, m.latsOff,         m.latsLen),
        depths:       new Int32Array  (m.buffer, m.depthsOff,       m.depthsLen),
        operatorIdxs: new Uint16Array (m.buffer, m.operatorIdxsOff, m.operatorIdxsLen),
        countyIdxs:   new Uint16Array (m.buffer, m.countyIdxsOff,   m.countyIdxsLen),
        statusIdxs:   new Uint8Array  (m.buffer, m.statusIdxsOff,   m.statusIdxsLen),
        wellTypeIdxs: new Uint8Array  (m.buffer, m.wellTypeIdxsOff, m.wellTypeIdxsLen),
        sourceIdxs:   new Uint8Array  (m.buffer, m.sourceIdxsOff,   m.sourceIdxsLen),
        spudDateIdxs: new Uint16Array (m.buffer, m.spudDateIdxsOff, m.spudDateIdxsLen),
      };

      const attrs: PrebuiltAttrs = {
        positions:     m.positions,
        lineWidths:    m.lineWidths,
        lineColors:    m.lineColors,
        fillColors:    new Uint8Array(0),
        elevations:    m.elevations,
        depthColors:   m.depthColors,
        filteredCount: 0,
        filterKey:     "",
        rawCounts:     m.rawCounts,
      };

      resolve({ cols, attrs });
    };

    worker.onerror = (e) => {
      worker.terminate();
      reject(new Error(e.message || "wells worker error"));
    };

    // Transfer the buffer to the worker (zero-copy)
    worker.postMessage({ buffer, stateKey: _stateKey, compressed }, [buffer]);
  });
}
