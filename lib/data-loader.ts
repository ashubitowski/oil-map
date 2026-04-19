const cache: Record<string, unknown> = {};
const binCache: Record<string, ArrayBuffer> = {};

export async function loadGeoJSON(path: string) {
  if (cache[path]) return cache[path];
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  const data = await res.json();
  cache[path] = data;
  return data;
}

export async function loadJSON<T>(path: string): Promise<T> {
  if (cache[path]) return cache[path] as T;
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  const data = await res.json();
  cache[path] = data;
  return data;
}

export async function loadBin(path: string): Promise<ArrayBuffer> {
  if (binCache[path]) return binCache[path];
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  const buf = await res.arrayBuffer();
  binCache[path] = buf;
  return buf;
}
