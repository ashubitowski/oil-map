import {
  decodeWellsBin,
  buildPositions,
  buildLineWidths,
  buildLineColors,
  countByStatus,
} from "./wells-binary";

interface WorkerInput {
  buffer: ArrayBuffer;
  stateKey: string;
  compressed: boolean;
}

function depthToColorRGBA(depth_ft: number): [number, number, number, number] {
  const stops: [number, [number, number, number]][] = [
    [0,     [0,   220, 255]],
    [5000,  [59,  130, 246]],
    [10000, [29,  78,  216]],
    [20000, [15,  23,  42 ]],
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

function buildElevations(depths: Int32Array): Float32Array {
  const out = new Float32Array(depths.length);
  for (let i = 0; i < depths.length; i++) out[i] = depths[i] / 10;
  return out;
}

function buildDepthColors(depths: Int32Array): Uint8Array {
  const out = new Uint8Array(depths.length * 4);
  for (let i = 0; i < depths.length; i++) {
    if (depths[i] === 0) continue; // alpha stays 0 — hidden in 3D, visible in 2D
    const [r, g, b, a] = depthToColorRGBA(depths[i]);
    out[i * 4]     = r;
    out[i * 4 + 1] = g;
    out[i * 4 + 2] = b;
    out[i * 4 + 3] = a;
  }
  return out;
}

self.onmessage = async (e: MessageEvent<WorkerInput>) => {
  const { buffer, stateKey, compressed } = e.data;

  const raw = compressed
    ? await new Response(
        new Blob([buffer]).stream().pipeThrough(new DecompressionStream("gzip"))
      ).arrayBuffer()
    : buffer;

  const cols = decodeWellsBin(raw);

  const positions  = buildPositions(cols);
  const lineWidths = buildLineWidths(cols);
  const lineColors = buildLineColors(cols);
  const rawCounts  = countByStatus(cols);
  const elevations = buildElevations(cols.depths);
  const depthColors = buildDepthColors(cols.depths);

  const msg = {
    stateKey,
    // Return the raw (possibly decompressed) buffer so main thread can reconstruct typed-array views
    buffer: raw,
    count: cols.count,
    state: cols.state,
    ids:   cols.ids,
    dicts: cols.dicts,
    // Byte offsets + lengths for every column (all share the same buffer)
    lonsOff:         cols.lons.byteOffset,         lonsLen:         cols.lons.length,
    latsOff:         cols.lats.byteOffset,         latsLen:         cols.lats.length,
    depthsOff:       cols.depths.byteOffset,       depthsLen:       cols.depths.length,
    operatorIdxsOff: cols.operatorIdxs.byteOffset, operatorIdxsLen: cols.operatorIdxs.length,
    countyIdxsOff:   cols.countyIdxs.byteOffset,   countyIdxsLen:   cols.countyIdxs.length,
    statusIdxsOff:   cols.statusIdxs.byteOffset,   statusIdxsLen:   cols.statusIdxs.length,
    wellTypeIdxsOff: cols.wellTypeIdxs.byteOffset, wellTypeIdxsLen: cols.wellTypeIdxs.length,
    sourceIdxsOff:   cols.sourceIdxs.byteOffset,   sourceIdxsLen:   cols.sourceIdxs.length,
    spudDateIdxsOff: cols.spudDateIdxs.byteOffset, spudDateIdxsLen: cols.spudDateIdxs.length,
    // Prebuilt attribute arrays (independently owned buffers)
    positions,
    lineWidths,
    lineColors,
    elevations,
    depthColors,
    rawCounts,
  };

  // Transfer: raw buffer + each prebuilt attr's independently owned buffer (zero-copy)
  (self as unknown as Worker).postMessage(msg, [
    raw,
    positions.buffer,
    lineWidths.buffer,
    lineColors.buffer,
    elevations.buffer,
    depthColors.buffer,
  ]);
};
