"use client";

import { LayerState } from "@/lib/types";

interface Props {
  layers: LayerState;
  selectedMonth?: string;
  hasOffshore?: boolean;
  isOverview?: boolean;
  isDensityOverview?: boolean;
  filteredCount?: number;
  totalCount?: number;
}

export default function Legend({ layers, selectedMonth, hasOffshore, isOverview, isDensityOverview, filteredCount, totalCount }: Props) {
  const visible = layers.plays || layers.probability || layers.production || layers.wells;
  if (!visible) return null;

  const monthLabel = selectedMonth
    ? new Date(selectedMonth + "-01").toLocaleDateString("en-US", { month: "short", year: "numeric" })
    : null;

  return (
    <div className="absolute bottom-8 right-4 z-10 bg-gray-950/90 border border-gray-800 rounded-lg p-3 space-y-3 min-w-[160px] max-w-[200px] backdrop-blur-sm shadow-xl">
      {layers.plays && (
        <div>
          <p className="text-xs text-gray-400 mb-1.5">Shale Plays</p>
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-4 h-3 rounded-sm border border-amber-500/80 bg-amber-500/25" />
            <span className="text-xs text-gray-500">Play polygon</span>
          </div>
        </div>
      )}
      {layers.probability && (
        <div>
          <p className="text-xs text-gray-400 mb-1.5">Oil Probability</p>
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-24 rounded-sm" style={{ background: "linear-gradient(to right, #1a4731, #22c55e, #fbbf24, #ef4444)" }} />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-0.5">
            <span>Low</span><span>High</span>
          </div>
        </div>
      )}
      {layers.wells && (
        <div>
          <p className="text-xs text-gray-400 mb-1.5">Well Depth</p>
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-24 rounded-sm" style={{ background: "linear-gradient(to right, #93c5fd, #1d4ed8, #0f172a)" }} />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-0.5">
            <span>Shallow</span><span>Deep</span>
          </div>
          {isOverview && (
            <p className="text-xs text-gray-500 mt-1">Overview · zoom in for all wells</p>
          )}
          {!isOverview && filteredCount !== undefined && totalCount !== undefined && filteredCount < totalCount && (
            <p className="text-xs text-gray-500 mt-1">
              {filteredCount.toLocaleString()} / {totalCount.toLocaleString()} wells
            </p>
          )}
          {hasOffshore && (
            <div className="flex items-center gap-1.5 mt-1.5">
              <span className="inline-block w-3 h-3 rounded-full border border-cyan-400 bg-transparent" />
              <span className="text-xs text-gray-500">Offshore (BOEM)</span>
            </div>
          )}
          {layers.wells3d && isDensityOverview && (
            <p className="text-xs text-gray-500 mt-1">Density view · zoom in for per-well depth</p>
          )}
          {layers.wells3d && !isDensityOverview && (
            <p className="text-xs text-gray-600 mt-1">3D columns enabled</p>
          )}
          {layers.waterWells && (
            <p className="text-xs text-gray-600 mt-1">Incl. water & monitoring wells (CT, DE, HI, MA, ME, NH, RI, SC, VT, WI)</p>
          )}
        </div>
      )}
      {layers.production && (
        <div>
          <p className="text-xs text-gray-400 mb-1.5">Production (bbl/d)</p>
          <div className="flex items-center gap-2">
            <span className="inline-block rounded-full bg-red-500 opacity-75" style={{ width: 10, height: 10 }} />
            <span className="text-xs text-gray-500">Small basin</span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="inline-block rounded-full bg-red-500 opacity-75" style={{ width: 22, height: 22 }} />
            <span className="text-xs text-gray-500">Major basin</span>
          </div>
          {monthLabel && (
            <p className="text-xs text-gray-600 mt-1.5">{monthLabel}</p>
          )}
          <p className="text-xs text-gray-600 mt-0.5">Click bubble for details</p>
        </div>
      )}
    </div>
  );
}
