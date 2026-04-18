"use client";

import { LayerState } from "@/lib/types";

interface Props {
  layers: LayerState;
}

export default function Legend({ layers }: Props) {
  const visible = layers.probability || layers.production || layers.wells;
  if (!visible) return null;

  return (
    <div className="absolute bottom-8 right-4 z-10 bg-gray-900/90 border border-gray-700 rounded-lg p-3 space-y-3 min-w-[160px]">
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
          <p className="text-xs text-gray-600 mt-1.5">Click bubble for details</p>
        </div>
      )}
    </div>
  );
}
