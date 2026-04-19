"use client";

import { LayerId, LayerState, WellStatus } from "@/lib/types";
import WellStatusFilter from "./WellStatusFilter";

const LAYERS: { id: LayerId; label: string; color: string }[] = [
  { id: "plays", label: "Shale Plays", color: "bg-amber-500" },
  { id: "wells", label: "Wells + Depth", color: "bg-blue-500" },
  { id: "probability", label: "Oil Probability", color: "bg-green-500" },
  { id: "production", label: "Production", color: "bg-red-500" },
];

interface Props {
  layers: LayerState;
  onToggle: (id: LayerId) => void;
  enabledStatuses?: Set<WellStatus>;
  statusCounts?: Partial<Record<WellStatus, number>>;
  onStatusToggle?: (status: WellStatus) => void;
  onStatusReset?: () => void;
}

export default function LayerToggle({ layers, onToggle, enabledStatuses, statusCounts, onStatusToggle, onStatusReset }: Props) {
  return (
    <div className="absolute top-4 right-4 z-10 bg-gray-900/90 border border-gray-700 rounded-lg p-3 space-y-2 min-w-[180px]">
      <p className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">Layers</p>
      {LAYERS.map(({ id, label, color }) => (
        <div key={id}>
          <button
            onClick={() => onToggle(id)}
            aria-label={`${layers[id] ? "Hide" : "Show"} ${label} layer`}
            aria-pressed={layers[id]}
            className={`flex items-center gap-2 w-full text-sm text-left transition-opacity ${
              layers[id] ? "opacity-100" : "opacity-40"
            }`}
          >
            <span className={`w-3 h-3 rounded-sm flex-shrink-0 ${color}`} />
            <span className="text-gray-200">{label}</span>
          </button>
          {id === "wells" && layers.wells && (
            <>
              <button
                onClick={() => onToggle("wells3d")}
                aria-label={`${layers.wells3d ? "Disable" : "Enable"} 3D depth columns`}
                aria-pressed={layers.wells3d}
                className={`flex items-center gap-2 w-full text-xs text-left mt-1 pl-5 transition-opacity ${
                  layers.wells3d ? "opacity-100" : "opacity-40"
                }`}
              >
                <span className="w-2 h-2 rounded-sm flex-shrink-0 bg-blue-400 border border-blue-300" />
                <span className="text-gray-400">3D depth columns</span>
              </button>
              {enabledStatuses && onStatusToggle && onStatusReset && (
                <WellStatusFilter
                  enabledStatuses={enabledStatuses}
                  counts={statusCounts ?? {}}
                  onToggle={onStatusToggle}
                  onReset={onStatusReset}
                />
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}
