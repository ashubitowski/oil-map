"use client";

import { WellStatus, WELL_STATUSES } from "@/lib/types";

interface Props {
  enabledStatuses: Set<WellStatus>;
  counts: Partial<Record<WellStatus, number>>;
  onToggle: (status: WellStatus) => void;
  onReset: () => void;
}

const STATUS_COLORS: Record<WellStatus, string> = {
  "Active":              "#22c55e",
  "Inactive":            "#f59e0b",
  "Plugged & Abandoned": "#6b7280",
  "Permitted":           "#a855f7",
  "Unknown":             "#4b5563",
};

const STATUS_LABELS: Record<WellStatus, string> = {
  "Active":              "Active",
  "Inactive":            "Inactive",
  "Plugged & Abandoned": "P&A",
  "Permitted":           "Permitted",
  "Unknown":             "Unknown",
};

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

export default function WellStatusFilter({ enabledStatuses, counts, onToggle, onReset }: Props) {
  const isDefault = enabledStatuses.size === 1 && enabledStatuses.has("Active");

  return (
    <div className="mt-2 pt-2 border-t border-gray-700">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-gray-500 uppercase tracking-wider">Status</span>
        {!isDefault && (
          <button
            onClick={onReset}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            Reset
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1">
        {WELL_STATUSES.map((status) => {
          const enabled = enabledStatuses.has(status);
          const count = counts[status];
          const color = STATUS_COLORS[status];
          return (
            <button
              key={status}
              onClick={() => onToggle(status)}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs transition-all ${
                enabled
                  ? "bg-gray-700 text-gray-200"
                  : "bg-gray-800 text-gray-500 opacity-60"
              }`}
            >
              <span
                className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: enabled ? color : "#374151" }}
              />
              <span>{STATUS_LABELS[status]}</span>
              {count !== undefined && count > 0 && (
                <span className="text-gray-400">{fmt(count)}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
