"use client";

import { useState } from "react";
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
  const [open, setOpen] = useState(true);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="absolute top-4 right-0 z-10 bg-gray-900/90 border border-r-0 border-gray-700 rounded-l-lg px-2.5 py-3 text-gray-400 hover:text-gray-200 transition-colors"
        aria-label="Show layers panel"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
      </button>
    );
  }

  return (
    <div className="absolute top-4 right-0 z-10 bg-gray-900/90 border border-r-0 border-gray-700 rounded-l-lg p-2.5 w-[185px]">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] text-gray-400 font-medium uppercase tracking-wider">Layers</p>
        <button
          onClick={() => setOpen(false)}
          className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
          aria-label="Hide layers panel"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
      <div className="space-y-1.5">
        {LAYERS.map(({ id, label, color }) => (
          <div key={id}>
            <button
              onClick={() => onToggle(id)}
              aria-label={`${layers[id] ? "Hide" : "Show"} ${label} layer`}
              aria-pressed={layers[id]}
              className={`flex items-center gap-1.5 w-full text-xs text-left transition-opacity ${
                layers[id] ? "opacity-100" : "opacity-40"
              }`}
            >
              <span className={`w-2.5 h-2.5 rounded-sm flex-shrink-0 ${color}`} />
              <span className="text-gray-200">{label}</span>
            </button>
            {id === "wells" && layers.wells && (
              <>
                <button
                  onClick={() => onToggle("wells3d")}
                  aria-label={`${layers.wells3d ? "Disable" : "Enable"} 3D depth columns`}
                  aria-pressed={layers.wells3d}
                  className={`flex items-center gap-1.5 w-full text-[11px] text-left mt-1 pl-4 transition-opacity ${
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
    </div>
  );
}
