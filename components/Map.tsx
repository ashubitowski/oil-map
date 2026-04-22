"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { LayerState, LayerId, Well, ProductionBasin, ProductionHistory, WellManifest } from "@/lib/types";
import { loadGeoJSON, loadJSON, loadBin, loadWellsState } from "@/lib/data-loader";
import type { PrebuiltAttrs } from "@/lib/data-loader";
import {
  WellColumns,
  decodeWellsBin,
  columnsToWell,
  findWellIndexById,
  buildPositions,
  buildFillColors,
  buildLineWidths,
  buildLineColors,
  buildStatusFilter,
  countByStatus,
} from "@/lib/wells-binary";
import { readUrlState, useUrlSync, type UrlSelection } from "@/lib/use-url-state";
import { WellStatus, WELL_STATUSES } from "@/lib/types";
import LayerToggle from "./LayerToggle";
import WellPopup from "./WellPopup";
import ProductionPopup from "./ProductionPopup";
import TimelineSlider from "./TimelineSlider";
import Legend from "./Legend";
import LoadBanner from "./LoadBanner";

declare global {
  interface Window {
    maplibregl: typeof import("maplibre-gl");
  }
}

const STYLE_URL =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const US_BOUNDS: [[number, number], [number, number]] = [
  [-130, 22],
  [-60, 52],
];

type Color4 = [number, number, number, number];

function depthToColor(depth_ft: number): Color4 {
  const stops: [number, [number, number, number]][] = [
    [0, [147, 197, 253]],
    [5000, [59, 130, 246]],
    [10000, [29, 78, 216]],
    [20000, [15, 23, 42]],
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

const COLUMN_MATERIAL = { ambient: 0.3, diffuse: 0.7, shininess: 48, specularColor: [90, 100, 120] as [number, number, number] };

export default function Map() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("maplibre-gl").Map | null>(null);
  const overlayRef = useRef<{ setProps: (p: { layers: unknown[] }) => void } | null>(null);
  const prevCameraRef = useRef<{ pitch: number; bearing: number }>({ pitch: 0, bearing: 0 });
  const cameraAutoSetRef = useRef(false);
  const productionHistoryRef = useRef<ProductionHistory | null>(null);
  const productionBasinsRef = useRef<ProductionBasin[] | null>(null);
  const productionMaxBpdRef = useRef<number>(0);
  const urlSelectionRef = useRef<UrlSelection | undefined>(
    typeof window !== "undefined" ? readUrlState().selection : undefined
  );
  const wellsDataRef = useRef<Well[]>([]);
  const wellColumnsRef = useRef<WellColumns | null>(null);
  const rebuildAndRenderRef = useRef<(() => void) | null>(null);
  const manifestRef = useRef<WellManifest | null>(null);
  const perStateColsRef = useRef<Record<string, WellColumns>>({});
  const perStateAttrsRef = useRef<Record<string, PrebuiltAttrs>>({});
  const stateStatusRef = useRef<Record<string, "idle" | "loading" | "loaded">>({});
  const overviewColsRef = useRef<WellColumns | null>(null);
  const overviewStatusRef = useRef<"idle" | "loading" | "loaded">("idle");
  const overviewAttrsRef = useRef<{ cols: WellColumns; positions: Float32Array; fillColors: Uint8Array; elevations: Float32Array } | null>(null);
  const [loadingStates, setLoadingStates] = useState<string[]>([]);
  const [mapZoom, setMapZoom] = useState<number>(4);

  const { syncLayers, syncViewport, syncSelection, syncMonth } = useUrlSync();
  const syncViewportRef = useRef(syncViewport);
  syncViewportRef.current = syncViewport;
  const syncSelectionRef = useRef(syncSelection);
  syncSelectionRef.current = syncSelection;


  const [loadErrors, setLoadErrors] = useState<Record<string, string>>({});
  const [hasOffshore, setHasOffshore] = useState(false);

  const reportLoadError = useCallback((layer: string, err: unknown) => {
    const msg = err instanceof Error ? err.message : "failed to load";
    setLoadErrors((prev) => ({ ...prev, [layer]: msg }));
  }, []);

  const [layers, setLayers] = useState<LayerState>(() => {
    const url = typeof window !== "undefined" ? readUrlState().layers : {};
    return {
      plays: url.plays ?? false,
      wells: url.wells ?? true,
      probability: url.probability ?? false,
      production: url.production ?? false,
      wells3d: url.wells3d ?? false,
      waterWells: url.waterWells ?? false,
    };
  });
  const [selectedWell, setSelectedWell] = useState<Well | null>(null);
  const [selectedBasin, setSelectedBasin] = useState<ProductionBasin | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string>(() =>
    typeof window !== "undefined" ? (readUrlState().month ?? "") : ""
  );
  const [productionMonths, setProductionMonths] = useState<string[]>([]);
  const [mapReady, setMapReady] = useState(false);
  const [enabledStatuses, setEnabledStatuses] = useState<Set<WellStatus>>(
    () => new Set<WellStatus>(["Active"])
  );
  const [statusCounts, setStatusCounts] = useState<Partial<Record<WellStatus, number>>>({});
  const enabledStatusesRef = useRef<Set<WellStatus>>(new Set<WellStatus>(["Active"]));

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    import("maplibre-gl").then((maplibre) => {
      const urlState = readUrlState();
      const mapOptions: ConstructorParameters<typeof maplibre.Map>[0] = {
        container: containerRef.current!,
        style: STYLE_URL,
      };
      if (urlState.viewport) {
        mapOptions.center = [urlState.viewport.lng, urlState.viewport.lat];
        mapOptions.zoom = urlState.viewport.zoom;
      } else {
        mapOptions.bounds = US_BOUNDS;
        mapOptions.fitBoundsOptions = { padding: 40 };
      }

      const map = new maplibre.Map(mapOptions);

      map.on("load", async () => {
        mapRef.current = map;
        // Store maplibre ref so we can use Popup elsewhere
        (map as unknown as { _ml: typeof maplibre })._ml = maplibre;

        // Navigation + scale controls
        map.addControl(new maplibre.NavigationControl(), "top-left");
        map.addControl(new maplibre.ScaleControl({ unit: "imperial" }), "bottom-left");

        // Atmospheric sky — invisible at pitch 0, dramatic at high pitch
        try {
          (map as unknown as { setSky: (s: object) => void }).setSky({
            "sky-color": "#0b1220",
            "horizon-color": "#1a2332",
            "fog-color": "#0b1220",
            "horizon-fog-blend": 0.6,
            "sky-horizon-blend": 0.8,
          });
        } catch {}

        // Create deck.gl overlay for 3D layers
        try {
          const [{ MapboxOverlay }, { LightingEffect, AmbientLight, DirectionalLight }] = await Promise.all([
            import("@deck.gl/mapbox"),
            import("@deck.gl/core"),
          ]);
          const lightingEffect = new LightingEffect({
            ambientLight: new AmbientLight({ color: [255, 230, 200], intensity: 0.55 }),
            sunLight: new DirectionalLight({ color: [255, 220, 180], intensity: 1.6, direction: [-1, -3, -2] }),
            rimLight: new DirectionalLight({ color: [120, 180, 255], intensity: 0.6, direction: [1, 2, -1] }),
          });
          const overlay = new MapboxOverlay({ layers: [], effects: [lightingEffect] });
          map.addControl(overlay as unknown as import("maplibre-gl").IControl);
          overlayRef.current = overlay as unknown as { setProps: (p: { layers: unknown[] }) => void };
        } catch {
          // deck.gl overlay unavailable — 3D wells will silently degrade
        }

        setMapReady(true);
      });

      map.on("moveend", () => {
        const c = map.getCenter();
        syncViewportRef.current({ lng: c.lng, lat: c.lat, zoom: map.getZoom() });
      });

      map.on("zoomend", () => setMapZoom(map.getZoom()));
    });

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // Plays layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    if (layers.plays) {
      loadGeoJSON("/data/plays.geojson")
        .then((data) => {
          if (!map.getSource("plays")) {
            map.addSource("plays", { type: "geojson", data: data as GeoJSON.FeatureCollection });
            map.addLayer({
              id: "plays-fill",
              type: "fill-extrusion",
              source: "plays",
              paint: {
                "fill-extrusion-color": "#f59e0b",
                "fill-extrusion-opacity": 0.28,
                "fill-extrusion-height": 25000,
                "fill-extrusion-base": 0,
              },
            });
            map.addLayer({
              id: "plays-outline",
              type: "line",
              source: "plays",
              paint: {
                "line-color": "#f59e0b",
                "line-width": 1.5,
                "line-opacity": 0.8,
              },
            });

            // Hover popup
            const ml = (map as unknown as { _ml: { Popup: typeof import("maplibre-gl").Popup } })._ml;
            const popup = new ml.Popup({
              closeButton: false,
              closeOnClick: false,
              className: "oil-popup",
            });

            map.on("mouseenter", "plays-fill", (e) => {
              map.getCanvas().style.cursor = "pointer";
              const props = e.features?.[0]?.properties ?? {};
              popup
                .setLngLat(e.lngLat)
                .setHTML(
                  `<div style="background:#1f2937;border:1px solid #374151;border-radius:6px;padding:8px 10px;color:#e5e7eb;font-size:12px;min-width:140px">
                    <div style="color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Shale Play</div>
                    <div style="font-weight:500">${props.Shale_play ?? props.name ?? "Unknown"}</div>
                  </div>`
                )
                .addTo(map);
            });

            map.on("mouseleave", "plays-fill", () => {
              map.getCanvas().style.cursor = "";
              popup.remove();
            });
          } else {
            map.setLayoutProperty("plays-fill", "visibility", "visible");
            map.setLayoutProperty("plays-outline", "visibility", "visible");
          }
        })
        .catch((err) => reportLoadError("plays", err));
    } else {
      if (map.getLayer("plays-fill")) {
        map.setLayoutProperty("plays-fill", "visibility", "none");
        map.setLayoutProperty("plays-outline", "visibility", "none");
      }
    }
  }, [layers.plays, mapReady]);

  // Wells layer — viewport-driven loading: only fetch states visible in the current map bounds
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    if (!layers.wells) {
      overlayRef.current?.setProps({ layers: [] });
      if (cameraAutoSetRef.current) {
        cameraAutoSetRef.current = false;
        map.flyTo({ pitch: prevCameraRef.current.pitch, bearing: prevCameraRef.current.bearing, duration: 1000 });
      }
      setSelectedWell(null);
      return;
    }

    const OVERVIEW_MAX_ZOOM = 6;

    const renderWells = async (syntheticWells: Well[], overviewCols: WellColumns | null) => {
      if (!overlayRef.current) return;
      const { ScatterplotLayer, ColumnLayer } = await import("@deck.gl/layers");
      const perStateCols = perStateColsRef.current;
      const filterKey = [...enabledStatusesRef.current].sort().join(",");

      if (layers.wells3d) {
        const deckLayers3d = [];
        const zoom = mapRef.current?.getZoom() ?? OVERVIEW_MAX_ZOOM;
        const crossT = Math.max(0, Math.min(1, zoom - 6.5));
        const overviewOpacity3d = (1 - crossT) * 0.9;
        const detailOpacity3d = crossT;

        // Overview ColumnLayer at low zoom — reuses the same overview binary buffer
        if (overviewCols && overviewCols.count > 0 && overviewOpacity3d > 0) {
          if (overviewAttrsRef.current?.cols !== overviewCols) {
            const elevs = new Float32Array(overviewCols.count);
            for (let i = 0; i < overviewCols.count; i++) elevs[i] = overviewCols.depths[i] / 10;
            overviewAttrsRef.current = {
              cols: overviewCols,
              positions:  buildPositions(overviewCols),
              fillColors: buildFillColors(overviewCols),
              elevations: elevs,
            };
          }
          const oAttrs = overviewAttrsRef.current!;
          deckLayers3d.push(
            new ColumnLayer({
              id: "wells-3d-overview",
              data: { length: overviewCols.count, attributes: {
                getPosition:  { value: oAttrs.positions,  size: 2 },
                getElevation: { value: oAttrs.elevations, size: 1 },
                getFillColor: { value: oAttrs.fillColors, size: 4, normalized: true },
              }},
              radius: 10000,
              diskResolution: 8,
              elevationScale: 150,
              opacity: overviewOpacity3d,
              transitions: { opacity: 400 },
              material: COLUMN_MATERIAL,
              pickable: false,
            })
          );
        }

        // Per-state ColumnLayers — fade in at zoom ≥ 6.5
        if (detailOpacity3d > 0) {
          for (const [key, cols] of Object.entries(perStateCols)) {
            const attrs = perStateAttrsRef.current[key];
            if (!attrs) continue;
            deckLayers3d.push(
              new ColumnLayer({
                id: `wells-3d-${key}`,
                data: { length: cols.count, attributes: {
                  getPosition:  { value: attrs.positions,   size: 2 },
                  getElevation: { value: attrs.elevations,  size: 1 },
                  getFillColor: { value: attrs.depthColors, size: 4, normalized: true },
                }},
                radius: 800,
                diskResolution: 8,
                elevationScale: 1,
                opacity: detailOpacity3d,
                transitions: { opacity: 400 },
                material: COLUMN_MATERIAL,
                pickable: true,
                onClick: (info: { index: number }) => {
                  if (info.index >= 0) {
                    const well = columnsToWell(cols, info.index);
                    setSelectedWell(well);
                    syncSelectionRef.current({ type: "well", id: well.id });
                  }
                },
              })
            );
          }

          // Synthetic wells (accessor path — small count)
          if (syntheticWells.length > 0) {
            deckLayers3d.push(
              new ColumnLayer({
                id: "wells-3d-synthetic",
                data: syntheticWells,
                getPosition: (d: Well) => [d.lon, d.lat],
                getElevation: (d: Well) => d.depth_ft / 10,
                getFillColor: (d: Well) => depthToColor(d.depth_ft),
                radius: 800,
                diskResolution: 8,
                elevationScale: 1,
                opacity: detailOpacity3d,
                transitions: { opacity: 400 },
                material: COLUMN_MATERIAL,
                pickable: true,
              })
            );
          }
        }

        overlayRef.current.setProps({ layers: deckLayers3d });
        if (!cameraAutoSetRef.current) {
          prevCameraRef.current = { pitch: map.getPitch(), bearing: map.getBearing() };
          cameraAutoSetRef.current = true;
          map.flyTo({
            pitch: 55,
            bearing: map.getBearing() + 15,
            duration: 1800,
            curve: 1.4,
            easing: (t: number) => t * (2 - t),
          });
        }
      } else {
        const zoom = mapRef.current?.getZoom() ?? OVERVIEW_MAX_ZOOM;
        // t=0 at zoom 5.5, t=1 at zoom 6.5 — crossfade window of 1°
        const t = Math.max(0, Math.min(1, zoom - 6.5));
        const overviewOpacity = (1 - t) * 0.85;
        const detailOpacity   = t * 0.75;

        const deckLayers = [];

        if (overviewCols && overviewCols.count > 0) {
          if (overviewAttrsRef.current?.cols !== overviewCols) {
            overviewAttrsRef.current = {
              cols: overviewCols,
              positions:  buildPositions(overviewCols),
              fillColors: buildFillColors(overviewCols),
              elevations: new Float32Array(0),
            };
          }
          const oAttrs2d = overviewAttrsRef.current!;
          const oPositions  = oAttrs2d.positions;
          const oFillColors = oAttrs2d.fillColors;
          deckLayers.push(
            new ScatterplotLayer({
              id: "wells-2d-overview",
              data: { length: overviewCols.count, attributes: {
                getPosition:  { value: oPositions,  size: 2 },
                getFillColor: { value: oFillColors, size: 4, normalized: true },
              }},
              radiusUnits: "pixels",
              getRadius: 4.5,
              opacity: overviewOpacity,
              transitions: { opacity: 400 },
              pickable: false,
              stroked: false,
            })
          );
        }

        // Per-state layers — no merge needed; stable arrays cached per state
        const aggregateCounts: Partial<Record<WellStatus, number>> = {};
        for (const [key, cols] of Object.entries(perStateCols)) {
          let attrs = perStateAttrsRef.current[key];
          if (!attrs) {
            attrs = {
              positions:   buildPositions(cols),
              lineWidths:  buildLineWidths(cols),
              lineColors:  buildLineColors(cols),
              fillColors:  new Uint8Array(0),
              elevations:  new Float32Array(0),
              depthColors: new Uint8Array(0),
              filteredCount: 0,
              filterKey: "",
              rawCounts: countByStatus(cols),
            };
          }
          if (attrs.filterKey !== filterKey) {
            const sf = buildStatusFilter(cols, enabledStatusesRef.current);
            attrs.fillColors = buildFillColors(cols, sf);
            attrs.filteredCount = sf.reduce((s, v) => s + v, 0);
            attrs.filterKey = filterKey;
          }
          perStateAttrsRef.current[key] = attrs;

          for (const [s, n] of Object.entries(attrs.rawCounts)) {
            aggregateCounts[s as WellStatus] = (aggregateCounts[s as WellStatus] ?? 0) + n;
          }

          if (detailOpacity > 0) deckLayers.push(
            new ScatterplotLayer({
              id: `wells-2d-real-${key}`,
              data: { length: cols.count, attributes: {
                getPosition:  { value: attrs.positions,  size: 2 },
                getFillColor: { value: attrs.fillColors,  size: 4, normalized: true },
                getLineWidth: { value: attrs.lineWidths,  size: 1 },
                getLineColor: { value: attrs.lineColors,  size: 4, normalized: true },
              }},
              radiusUnits: "pixels",
              getRadius: 3,
              opacity: detailOpacity,
              transitions: { opacity: 400 },
              pickable: true,
              stroked: true,
              lineWidthUnits: "pixels",
              onClick: (info) => {
                if (info.index >= 0) {
                  const well = columnsToWell(cols, info.index);
                  setSelectedWell(well);
                  syncSelectionRef.current({ type: "well", id: well.id });
                }
              },
              onHover: (info) => {
                map.getCanvas().style.cursor = info.index >= 0 ? "pointer" : "";
              },
            })
          );
        }

        setStatusCounts(aggregateCounts);

        const visibleSynthetic = syntheticWells.filter(
          (d) => enabledStatusesRef.current.has(d.status as WellStatus)
        );
        if (visibleSynthetic.length > 0) {
          deckLayers.push(
            new ScatterplotLayer({
              id: "wells-2d-synthetic",
              data: visibleSynthetic,
              getPosition: (d: Well) => [d.lon, d.lat],
              getFillColor: (d: Well) => depthToColor(d.depth_ft),
              radiusUnits: "pixels",
              getRadius: 3,
              opacity: detailOpacity,
              transitions: { opacity: 400 },
              pickable: true,
              stroked: true,
              lineWidthUnits: "pixels",
              getLineWidth: 0.5,
              getLineColor: [30, 58, 95, 150] as Color4,
              onClick: (info) => {
                const well = info.object as Well | null;
                if (well) {
                  setSelectedWell(well);
                  syncSelectionRef.current({ type: "well", id: well.id });
                }
              },
              onHover: (info) => {
                map.getCanvas().style.cursor = info.object ? "pointer" : "";
              },
            })
          );
        }

        overlayRef.current.setProps({ layers: deckLayers });

        if (cameraAutoSetRef.current) {
          cameraAutoSetRef.current = false;
          map.flyTo({ pitch: prevCameraRef.current.pitch, bearing: prevCameraRef.current.bearing, duration: 1000 });
        }
      }
    };

    // Re-render from per-state cache — no merge allocation
    const rebuildAndRender = () => {
      renderWells(wellsDataRef.current, overviewColsRef.current).catch(console.error);
    };
    rebuildAndRenderRef.current = rebuildAndRender;

    // Start loading any manifest states whose bbox intersects the current viewport
    const checkViewport = () => {
      if (!manifestRef.current) return;
      const bounds = map.getBounds();
      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();

      let startedAny = false;
      for (const [key, entry] of Object.entries(manifestRef.current.states)) {
        if (stateStatusRef.current[key] !== "idle") continue;
        if (entry.category === "water-other" && !layers.waterWells) continue;
        const [minLon, minLat, maxLon, maxLat] = entry.bbox;
        if (sw.lng >= maxLon || ne.lng <= minLon || sw.lat >= maxLat || ne.lat <= minLat) continue;

        stateStatusRef.current[key] = "loading";
        startedAny = true;
        setLoadingStates((prev) => [...prev, key]);

        const loadState: Promise<WellColumns | null> = entry.file.endsWith(".bin")
          ? loadWellsState(key, `/data/${entry.file}`).then(({ cols, attrs }) => {
              perStateColsRef.current[key] = cols;
              perStateAttrsRef.current[key] = attrs;
              return cols;
            })
          : loadJSON<Well[]>(`/data/${entry.file}`).then((wells) => {
              wellsDataRef.current = [...wellsDataRef.current, ...wells];
              return null;
            });

        loadState.then((cols) => {
          if (cols && urlSelectionRef.current?.type === "well") {
            const idx = findWellIndexById(cols, urlSelectionRef.current.id);
            if (idx >= 0) {
              setSelectedWell(columnsToWell(cols, idx));
              urlSelectionRef.current = undefined;
            }
          }
          stateStatusRef.current[key] = "loaded";
          setLoadingStates((prev) => prev.filter((k) => k !== key));
          rebuildAndRender();
        }).catch((err) => {
          stateStatusRef.current[key] = "idle";
          setLoadingStates((prev) => prev.filter((k) => k !== key));
          reportLoadError(`wells-${key.toLowerCase()}`, err);
        });
      }

      // No new loads started → all visible states are already loaded/loading; re-render with current data
      if (!startedAny) rebuildAndRender();
    };

    // Free memory for states whose bbox no longer intersects the viewport (+ 50% padding per side)
    const evictOffscreenStates = () => {
      if (!manifestRef.current) return;
      const bounds = map.getBounds();
      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();
      const lngPad = (ne.lng - sw.lng) * 0.5;
      const latPad = (ne.lat - sw.lat) * 0.5;
      const extMinLng = sw.lng - lngPad;
      const extMaxLng = ne.lng + lngPad;
      const extMinLat = sw.lat - latPad;
      const extMaxLat = ne.lat + latPad;

      let evictedAny = false;
      for (const [key, entry] of Object.entries(manifestRef.current.states)) {
        if (stateStatusRef.current[key] !== "loaded") continue;
        const [minLon, minLat, maxLon, maxLat] = entry.bbox;
        const intersects = !(extMinLng >= maxLon || extMaxLng <= minLon || extMinLat >= maxLat || extMaxLat <= minLat);
        if (!intersects) {
          delete perStateColsRef.current[key];
          delete perStateAttrsRef.current[key];
          stateStatusRef.current[key] = "idle";
          evictedAny = true;
        }
      }
      if (evictedAny) rebuildAndRender();
    };

    // When waterWells is toggled off, immediately evict any loaded water-other states
    if (!layers.waterWells && manifestRef.current) {
      let evicted = false;
      for (const [key, entry] of Object.entries(manifestRef.current.states)) {
        if (entry.category === "water-other" && stateStatusRef.current[key] === "loaded") {
          delete perStateColsRef.current[key];
          delete perStateAttrsRef.current[key];
          stateStatusRef.current[key] = "idle";
          evicted = true;
        }
      }
      if (evicted) rebuildAndRender();
    }

    // Load manifest + synthetic wells once, then check viewport
    const bootstrap = async () => {
      if (!manifestRef.current) {
        const manifest = await loadJSON<WellManifest>("/data/wells-manifest.json?v=10");
        manifestRef.current = manifest;
        for (const key of Object.keys(manifest.states)) {
          if (!(key in stateStatusRef.current)) stateStatusRef.current[key] = "idle";
        }
      }

      if (wellsDataRef.current.length === 0) {
        const [synWells, offshoreWells] = await Promise.all([
          loadJSON<Well[]>("/data/wells.json"),
          loadJSON<Well[]>("/data/wells-offshore.json").catch(() => [] as Well[]),
        ]);
        setHasOffshore((offshoreWells as Well[]).length > 0);
        const coveredStates = new Set(Object.keys(manifestRef.current!.states));
        wellsDataRef.current = [
          ...synWells.filter((w) => !coveredStates.has(w.state)),
          ...(offshoreWells as Well[]),
        ];
        if (urlSelectionRef.current?.type === "well") {
          const fallback = wellsDataRef.current.find((w) => w.id === urlSelectionRef.current!.id);
          if (fallback) { setSelectedWell(fallback); urlSelectionRef.current = undefined; }
        }
      }

      // Load overview once (fire-and-forget — don't block viewport check)
      if (overviewStatusRef.current === "idle") {
        overviewStatusRef.current = "loading";
        loadBin("/data/wells-overview.bin?v=10")
          .then((buf) => decodeWellsBin(buf))
          .then((cols) => {
            overviewColsRef.current = cols;
            overviewStatusRef.current = "loaded";
            rebuildAndRender();
          })
          .catch((err) => {
            overviewStatusRef.current = "idle";
            console.warn("[wells] overview load failed:", err);
          });
      }

      checkViewport();
    };

    let debounceTimer: ReturnType<typeof setTimeout> | null = null;
    const onMoveEnd = () => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        checkViewport();
        evictOffscreenStates();
      }, 250);
    };
    const onZoomEnd = () => rebuildAndRender();
    map.on("moveend", onMoveEnd);
    map.on("zoomend", onZoomEnd);

    bootstrap().catch((err) => { console.error("[wells] bootstrap error:", err); reportLoadError("wells", err); });

    return () => {
      map.off("moveend", onMoveEnd);
      map.off("zoomend", onZoomEnd);
      if (debounceTimer) clearTimeout(debounceTimer);
    };
  }, [layers.wells, layers.wells3d, layers.waterWells, mapReady]);

  // Probability layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    if (layers.probability) {
      loadGeoJSON("/data/assessment.geojson")
        .then((data) => {
          if (!map.getSource("probability")) {
            map.addSource("probability", { type: "geojson", data: data as GeoJSON.FeatureCollection });
            // Insert below plays-fill if it exists, otherwise just add
            const before = map.getLayer("plays-fill") ? "plays-fill" : undefined;
            map.addLayer(
              {
                id: "probability-fill",
                type: "fill",
                source: "probability",
                paint: {
                  "fill-color": [
                    "interpolate",
                    ["linear"],
                    ["get", "probability"],
                    0, "#14532d",
                    0.25, "#22c55e",
                    0.5, "#fbbf24",
                    1, "#ef4444",
                  ],
                  "fill-opacity": 0.5,
                },
              },
              before
            );

            // Hover tooltip
            const ml2 = (map as unknown as { _ml: { Popup: typeof import("maplibre-gl").Popup } })._ml;
            const probPopup = new ml2.Popup({ closeButton: false, closeOnClick: false });
            map.on("mouseenter", "probability-fill", (e) => {
              map.getCanvas().style.cursor = "crosshair";
              const props = e.features?.[0]?.properties ?? {};
              const tcf = typeof props.mean_resource_tcf === "number" ? props.mean_resource_tcf.toFixed(1) : "?";
              const prob = typeof props.probability === "number" ? Math.round(props.probability * 100) : "?";
              probPopup
                .setLngLat(e.lngLat)
                .setHTML(
                  `<div style="background:#1f2937;border:1px solid #374151;border-radius:6px;padding:8px 10px;color:#e5e7eb;font-size:12px;min-width:160px">
                    <div style="color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Oil Resource</div>
                    <div style="font-weight:500;margin-bottom:6px">${props.Shale_play ?? "Unknown"}</div>
                    <div style="display:flex;justify-content:space-between;color:#9ca3af">
                      <span>Est. resource</span><span style="color:#fbbf24">${tcf} TCF</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;color:#9ca3af;margin-top:2px">
                      <span>Relative probability</span><span style="color:#fbbf24">${prob}%</span>
                    </div>
                  </div>`
                )
                .addTo(map);
            });
            map.on("mouseleave", "probability-fill", () => {
              map.getCanvas().style.cursor = "";
              probPopup.remove();
            });
          } else {
            map.setLayoutProperty("probability-fill", "visibility", "visible");
          }
        })
        .catch((err) => reportLoadError("probability", err));
    } else {
      if (map.getLayer("probability-fill")) {
        map.setLayoutProperty("probability-fill", "visibility", "none");
      }
    }
  }, [layers.probability, mapReady]);

  // Production layer — sized circles at basin centroids
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    if (layers.production) {
      Promise.all([
        loadJSON<ProductionBasin[]>("/data/production-basins.json"),
        loadJSON<ProductionHistory>("/data/production-history.json"),
      ]).then(([basins, history]) => {
          productionHistoryRef.current = history;
          productionBasinsRef.current = basins;

          // Max bpd across all months and basins — keeps circle scale stable as slider moves
          const maxBpd = Math.max(
            ...Object.values(history).flatMap((entries) => entries.map((e) => e.bpd))
          );
          productionMaxBpdRef.current = maxBpd;

          // Extract ordered month list from any basin (all share the same range)
          const firstBasinHistory = Object.values(history)[0] ?? [];
          const months = firstBasinHistory.map((e) => e.month);
          const latestMonth = months[months.length - 1] ?? basins[0]?.month ?? "";

          setProductionMonths(months);
          setSelectedMonth((prev) => prev || latestMonth);

          const activeMonth = latestMonth;
          const geojson: GeoJSON.FeatureCollection = {
            type: "FeatureCollection",
            features: basins.map((b) => {
              const histEntry = history[b.name]?.find((e) => e.month === activeMonth);
              return {
                type: "Feature",
                geometry: { type: "Point", coordinates: [b.lon, b.lat] },
                properties: { ...b, bpd: histEntry?.bpd ?? b.bpd },
              };
            }),
          };

          if (!map.getSource("production")) {
            map.addSource("production", { type: "geojson", data: geojson });
            map.addLayer({
              id: "production-circles",
              type: "circle",
              source: "production",
              paint: {
                "circle-radius": [
                  "interpolate", ["linear"],
                  ["get", "bpd"],
                  0, 8,
                  maxBpd * 0.1, 18,
                  maxBpd * 0.5, 36,
                  maxBpd, 60,
                ],
                "circle-color": ["get", "color"],
                "circle-opacity": 0.75,
                "circle-stroke-width": 2,
                "circle-stroke-color": "#ffffff",
                "circle-stroke-opacity": 0.3,
              },
            });
            map.addLayer({
              id: "production-labels",
              type: "symbol",
              source: "production",
              layout: {
                "text-field": ["get", "name"],
                "text-size": 11,
                "text-offset": [0, 3.5],
                "text-anchor": "top",
              },
              paint: {
                "text-color": "#e5e7eb",
                "text-halo-color": "#111827",
                "text-halo-width": 1,
              },
            });

            map.on("click", "production-circles", (e) => {
              const props = e.features?.[0]?.properties as ProductionBasin;
              if (props) {
                // states may be JSON stringified in GeoJSON properties
                const basin = {
                  ...props,
                  states: typeof props.states === "string" ? JSON.parse(props.states) : props.states,
                };
                setSelectedBasin(basin);
                setSelectedWell(null);
                syncSelectionRef.current({ type: "basin", id: basin.id });
              }
            });
            map.on("mouseenter", "production-circles", () => {
              map.getCanvas().style.cursor = "pointer";
            });
            map.on("mouseleave", "production-circles", () => {
              map.getCanvas().style.cursor = "";
            });

            // Restore selection from URL
            if (urlSelectionRef.current?.type === "basin") {
              const basin = basins.find((b) => b.id === urlSelectionRef.current!.id);
              if (basin) {
                setSelectedBasin(basin);
                setSelectedWell(null);
              }
              urlSelectionRef.current = undefined;
            }
          } else {
            map.setLayoutProperty("production-circles", "visibility", "visible");
            map.setLayoutProperty("production-labels", "visibility", "visible");
          }
        })
        .catch((err) => reportLoadError("production", err));
    } else {
      if (map.getLayer("production-circles")) {
        map.setLayoutProperty("production-circles", "visibility", "none");
        map.setLayoutProperty("production-labels", "visibility", "none");
      }
      setSelectedBasin(null);
    }
  }, [layers.production, mapReady]);

  // Update production source data when selected month changes
  useEffect(() => {
    const map = mapRef.current;
    const history = productionHistoryRef.current;
    const basins = productionBasinsRef.current;
    if (!map || !mapReady || !selectedMonth || !history || !basins) return;
    const source = map.getSource("production") as { setData: (d: GeoJSON.FeatureCollection) => void } | undefined;
    if (!source) return;

    const geojson: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: basins.map((b) => {
        const histEntry = history[b.name]?.find((e) => e.month === selectedMonth);
        return {
          type: "Feature",
          geometry: { type: "Point", coordinates: [b.lon, b.lat] },
          properties: { ...b, bpd: histEntry?.bpd ?? b.bpd },
        };
      }),
    };
    source.setData(geojson);
  }, [selectedMonth, mapReady]);

  // Sync selected month to URL whenever it settles (handles initial history load)
  useEffect(() => {
    if (selectedMonth) syncMonth(selectedMonth);
  }, [selectedMonth, syncMonth]);

  const layersRef = useRef(layers);
  layersRef.current = layers;

  // Keep ref in sync and trigger re-render when filter changes
  useEffect(() => {
    enabledStatusesRef.current = enabledStatuses;
    rebuildAndRenderRef.current?.();
  }, [enabledStatuses]);

  // Auto-close popup when selected well's status gets filtered out
  useEffect(() => {
    if (selectedWell && !enabledStatuses.has(selectedWell.status as WellStatus)) {
      setSelectedWell(null);
    }
  }, [enabledStatuses, selectedWell]);

  const toggleStatus = useCallback((status: WellStatus) => {
    setEnabledStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(status)) {
        if (next.size === 1) return prev; // keep at least one
        next.delete(status);
      } else {
        next.add(status);
      }
      return next;
    });
  }, []);

  const resetStatuses = useCallback(() => {
    setEnabledStatuses(new Set<WellStatus>(["Active"]));
  }, []);

  const toggleLayer = useCallback((id: LayerId) => {
    const next = { ...layersRef.current, [id]: !layersRef.current[id] };
    setLayers(next);
    syncLayers(next);
  }, [syncLayers]);

  const handleMonthChange = useCallback((month: string) => {
    setSelectedMonth(month);
    syncMonth(month);
  }, [syncMonth]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />
      {mapReady && (
        <>
          <LayerToggle
            layers={layers}
            onToggle={toggleLayer}
            enabledStatuses={enabledStatuses}
            statusCounts={statusCounts}
            onStatusToggle={toggleStatus}
            onStatusReset={resetStatuses}
          />
          <Legend
            layers={layers}
            selectedMonth={selectedMonth || undefined}
            hasOffshore={hasOffshore}
            isOverview={layers.wells && mapZoom < 6}
            isDensityOverview={layers.wells3d && mapZoom < 6.5}
            filteredCount={Object.keys(perStateColsRef.current).length > 0 ? Array.from(enabledStatuses).reduce((s, st) => s + (statusCounts[st] ?? 0), 0) : undefined}
            totalCount={Object.values(statusCounts).reduce((a, b) => a + (b ?? 0), 0) || undefined}
          />
          <LoadBanner errors={loadErrors} loading={loadingStates} />
          {selectedWell && (
            <WellPopup
              well={selectedWell}
              onClose={() => { setSelectedWell(null); syncSelection(null); }}
            />
          )}
          {layers.production && productionMonths.length > 0 && (
            <TimelineSlider
              months={productionMonths}
              selectedMonth={selectedMonth}
              onChange={handleMonthChange}
            />
          )}
          {selectedBasin && !selectedWell && (
            <ProductionPopup
              basin={selectedBasin}
              history={productionHistoryRef.current?.[selectedBasin.name]}
              selectedMonth={selectedMonth || selectedBasin.month}
              onClose={() => { setSelectedBasin(null); syncSelection(null); }}
            />
          )}
        </>
      )}
      {!mapReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-950">
          <p className="text-gray-500 text-sm">Loading map…</p>
        </div>
      )}
    </div>
  );
}
