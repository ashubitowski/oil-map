"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { LayerState, LayerId, Well, ProductionBasin, ProductionHistory, WellManifest } from "@/lib/types";
import { loadGeoJSON, loadJSON, loadBin } from "@/lib/data-loader";
import {
  WellColumns,
  decodeWellsBin,
  columnsToWell,
  findWellIndexById,
  buildPositions,
  buildFillColors,
  buildLineWidths,
  buildLineColors,
  mergeBinaryColumns,
} from "@/lib/wells-binary";
import { readUrlState, useUrlSync, type UrlSelection } from "@/lib/use-url-state";
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

export default function Map() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("maplibre-gl").Map | null>(null);
  const overlayRef = useRef<{ setProps: (p: { layers: unknown[] }) => void } | null>(null);
  const prevPitchRef = useRef<number>(0);
  const pitchAutoSetRef = useRef(false);
  const productionHistoryRef = useRef<ProductionHistory | null>(null);
  const productionBasinsRef = useRef<ProductionBasin[] | null>(null);
  const productionMaxBpdRef = useRef<number>(0);
  const urlSelectionRef = useRef<UrlSelection | undefined>(
    typeof window !== "undefined" ? readUrlState().selection : undefined
  );
  const wellsDataRef = useRef<Well[]>([]);
  const wellColumnsRef = useRef<WellColumns | null>(null);

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
      plays: url.plays ?? true,
      wells: url.wells ?? false,
      probability: url.probability ?? false,
      production: url.production ?? false,
      wells3d: url.wells3d ?? false,
    };
  });
  const [selectedWell, setSelectedWell] = useState<Well | null>(null);
  const [selectedBasin, setSelectedBasin] = useState<ProductionBasin | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string>(() =>
    typeof window !== "undefined" ? (readUrlState().month ?? "") : ""
  );
  const [productionMonths, setProductionMonths] = useState<string[]>([]);
  const [mapReady, setMapReady] = useState(false);

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

        // Create deck.gl overlay for 3D layers
        try {
          const { MapboxOverlay } = await import("@deck.gl/mapbox");
          const overlay = new MapboxOverlay({ layers: [] });
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
              type: "fill",
              source: "plays",
              paint: {
                "fill-color": "#f59e0b",
                "fill-opacity": 0.25,
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

  // Wells layer — all rendering via deck.gl overlay (GPU buffers, no MapLibre GeoJSON source)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    if (layers.wells) {
      const renderWells = async (cols: WellColumns | null, syntheticWells: Well[]) => {
        if (!overlayRef.current) return;
        const { ScatterplotLayer, ColumnLayer } = await import("@deck.gl/layers");

        if (layers.wells3d) {
          // 3D mode: accessor-based for simplicity (rarely used)
          const allWells = cols
            ? [...syntheticWells, ...Array.from({ length: cols.count }, (_, i) => columnsToWell(cols, i))]
            : syntheticWells;
          overlayRef.current.setProps({
            layers: [
              new ColumnLayer({
                id: "wells-3d",
                data: allWells,
                getPosition: (d: Well) => [d.lon, d.lat],
                getElevation: (d: Well) => d.depth_ft / 10,
                getFillColor: (d: Well) => depthToColor(d.depth_ft),
                radius: 800,
                diskResolution: 6,
                elevationScale: 1,
                pickable: true,
              }),
            ],
          });
          if (!pitchAutoSetRef.current) {
            prevPitchRef.current = map.getPitch();
            pitchAutoSetRef.current = true;
            map.easeTo({ pitch: 45 });
          }
        } else {
          const deckLayers = [];

          // Real state wells — binary attributes, zero accessor calls
          if (cols && cols.count > 0) {
            const positions  = buildPositions(cols);
            const fillColors = buildFillColors(cols);
            const lineWidths = buildLineWidths(cols);
            const lineColors = buildLineColors(cols);

            deckLayers.push(
              new ScatterplotLayer({
                id: "wells-2d-real",
                data: { length: cols.count, attributes: {
                  getPosition:  { value: positions,  size: 2 },
                  getFillColor: { value: fillColors,  size: 4, normalized: true },
                  getLineWidth: { value: lineWidths,  size: 1 },
                  getLineColor: { value: lineColors,  size: 4, normalized: true },
                }},
                radiusUnits: "pixels",
                getRadius: 3,
                opacity: 0.75,
                pickable: true,
                stroked: true,
                lineWidthUnits: "pixels",
                onClick: (info) => {
                  if (info.index >= 0 && cols) {
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

          // Synthetic wells — small count, accessor-based
          if (syntheticWells.length > 0) {
            deckLayers.push(
              new ScatterplotLayer({
                id: "wells-2d-synthetic",
                data: syntheticWells,
                getPosition: (d: Well) => [d.lon, d.lat],
                getFillColor: (d: Well) => depthToColor(d.depth_ft),
                radiusUnits: "pixels",
                getRadius: 3,
                opacity: 0.75,
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

          if (pitchAutoSetRef.current) {
            pitchAutoSetRef.current = false;
            map.easeTo({ pitch: prevPitchRef.current });
          }
        }
      };

      const loadAndRender = async () => {
        if (wellsDataRef.current.length === 0 && !wellColumnsRef.current) {
          const manifest = await loadJSON<WellManifest>("/data/wells-manifest.json");
          const stateEntries = Object.entries(manifest.states).filter(
            ([key]) => key !== "OFFSHORE"
          );
          const binEntries = stateEntries.filter(([, e]) => e.file.endsWith(".bin"));
          const jsonEntries = stateEntries.filter(([, e]) => !e.file.endsWith(".bin"));

          const [syntheticWells, offshoreWells, ...stateResults] = await Promise.all([
            loadJSON<Well[]>("/data/wells.json"),
            loadJSON<Well[]>("/data/wells-offshore.json").catch(() => [] as Well[]),
            ...binEntries.map(([key, e]) => loadBin(`/data/${e.file}`).then(buf => {
              try { return decodeWellsBin(buf); }
              catch (err) { throw new Error(`${key} (${e.file}): ${err instanceof Error ? err.message : err}`); }
            })),
            ...jsonEntries.map(([, e]) => loadJSON<Well[]>(`/data/${e.file}`).catch(() => [] as Well[])),
          ]) as [Well[], Well[], ...(WellColumns | Well[])[]];

          setHasOffshore((offshoreWells as Well[]).length > 0);

          const binCols   = stateResults.slice(0, binEntries.length) as WellColumns[];
          const jsonWells = stateResults.slice(binEntries.length) as Well[][];

          // Merge binary columns — pick the first (or null if none); multi-state merge handled in Stage 3+
          // For now, concatenate all into one via a simple flat decode
          let mergedCols: WellColumns | null = null;
          if (binCols.length > 0) {
            if (binCols.length === 1) {
              mergedCols = binCols[0];
            } else {
              // Multi-state: concatenate typed arrays (dicts will be correct since each file
              // has its own dicts embedded; we keep per-column refs and decode on click)
              mergedCols = mergeBinaryColumns(binCols);
            }
          }
          wellColumnsRef.current = mergedCols;

          const coveredStates = new Set(stateEntries.map(([k]) => k));
          const synthetic = (syntheticWells as Well[]).filter((w) => !coveredStates.has(w.state));
          const jsonFlat  = jsonWells.flat();
          const offshoreArr = offshoreWells as Well[];
          wellsDataRef.current = [...synthetic, ...jsonFlat, ...offshoreArr];

          // URL restoration
          if (urlSelectionRef.current?.type === "well") {
            const targetId = urlSelectionRef.current.id;
            if (mergedCols) {
              const idx = findWellIndexById(mergedCols, targetId);
              if (idx >= 0) setSelectedWell(columnsToWell(mergedCols, idx));
            }
            if (!selectedWell) {
              const fallback = wellsDataRef.current.find((w) => w.id === targetId);
              if (fallback) setSelectedWell(fallback);
            }
            urlSelectionRef.current = undefined;
          }
        }

        await renderWells(wellColumnsRef.current, wellsDataRef.current);
      };

      loadAndRender().catch((err) => { console.error("[wells] load error:", err); reportLoadError("wells", err); });
    } else {
      overlayRef.current?.setProps({ layers: [] });
      if (pitchAutoSetRef.current) {
        pitchAutoSetRef.current = false;
        map.easeTo({ pitch: prevPitchRef.current });
      }
      setSelectedWell(null);
    }
  }, [layers.wells, layers.wells3d, mapReady]);

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
          <LayerToggle layers={layers} onToggle={toggleLayer} />
          <Legend layers={layers} selectedMonth={selectedMonth || undefined} hasOffshore={hasOffshore} />
          <LoadBanner errors={loadErrors} />
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
