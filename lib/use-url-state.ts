"use client";

import { useCallback, useRef } from "react";
import type { LayerState } from "./types";

export interface UrlViewport {
  lng: number;
  lat: number;
  zoom: number;
}

export interface UrlSelection {
  type: "well" | "basin";
  id: string;
}

export interface ParsedUrlState {
  layers: Partial<LayerState>;
  viewport?: UrlViewport;
  selection?: UrlSelection;
  month?: string;
}

const LAYER_KEYS: Array<keyof LayerState> = ["plays", "wells", "probability", "production", "wells3d"];

function serializeLayers(layers: LayerState): string {
  return LAYER_KEYS.map((k) => (layers[k] ? "1" : "0")).join("");
}

function parseLayers(l: string | null): Partial<LayerState> {
  if (!l || l.length !== LAYER_KEYS.length) return {};
  const result: Partial<LayerState> = {};
  LAYER_KEYS.forEach((k, i) => {
    result[k] = l[i] === "1";
  });
  return result;
}

export function readUrlState(): ParsedUrlState {
  if (typeof window === "undefined") return { layers: {} };
  const params = new URLSearchParams(window.location.search);

  const layers = parseLayers(params.get("l"));

  let viewport: UrlViewport | undefined;
  const v = params.get("v");
  if (v) {
    const parts = v.split(",").map(Number);
    if (parts.length === 3 && parts.every(isFinite)) {
      viewport = { lng: parts[0], lat: parts[1], zoom: parts[2] };
    }
  }

  let selection: UrlSelection | undefined;
  const sel = params.get("sel");
  if (sel?.startsWith("w:")) selection = { type: "well", id: sel.slice(2) };
  else if (sel?.startsWith("b:")) selection = { type: "basin", id: sel.slice(2) };

  const month = params.get("m") ?? undefined;

  return { layers, viewport, selection, month };
}

function updateParams(updates: Record<string, string | null>) {
  const params = new URLSearchParams(window.location.search);
  for (const [k, v] of Object.entries(updates)) {
    if (v === null) params.delete(k);
    else params.set(k, v);
  }
  const search = params.toString();
  const newUrl = search ? "?" + search : window.location.pathname;
  const current = window.location.search || "";
  if (current !== (search ? "?" + search : "")) {
    window.history.replaceState(null, "", newUrl);
  }
}

export function useUrlSync() {
  const viewportTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const syncLayers = useCallback((layers: LayerState) => {
    updateParams({ l: serializeLayers(layers) });
  }, []);

  const syncViewport = useCallback((viewport: UrlViewport) => {
    if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current);
    viewportTimerRef.current = setTimeout(() => {
      const { lng, lat, zoom } = viewport;
      updateParams({ v: `${lng.toFixed(4)},${lat.toFixed(4)},${zoom.toFixed(2)}` });
    }, 250);
  }, []);

  const syncSelection = useCallback((sel: UrlSelection | null) => {
    updateParams({ sel: sel ? `${sel.type === "well" ? "w" : "b"}:${sel.id}` : null });
  }, []);

  const syncMonth = useCallback((month: string) => {
    updateParams({ m: month });
  }, []);

  return { syncLayers, syncViewport, syncSelection, syncMonth };
}
