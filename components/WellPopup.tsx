"use client";

import { Well } from "@/lib/types";

interface Props {
  well: Well;
  onClose: () => void;
}

const SOURCE_LABELS: Record<string, string> = {
  synthetic: "Synthetic",
  rrc: "TX RRC",
  boem: "BOEM OCS",
  "nd-ogic": "ND OGIC",
  "co-ecmc": "CO ECMC",
  "ks-kgs": "KS KGS",
  "wy-wogcc": "WY WOGCC",
  "nm-ocd": "NM OCD",
  "ca-calgem": "CA CalGEM",
  "ok-occ": "OK OCC",
};

export default function WellPopup({ well, onClose }: Props) {
  return (
    <div className="absolute top-20 left-4 z-10 bg-gray-900/95 border border-gray-700 rounded-lg p-4 min-w-[220px]">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">Well</p>
          {well.source && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
              {SOURCE_LABELS[well.source] ?? well.source}
            </span>
          )}
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-sm leading-none">✕</button>
      </div>
      <div className="space-y-1.5">
        <Row label="Depth" value={well.depth_ft > 0 ? `${well.depth_ft.toLocaleString()} ft` : "—"} highlight />
        {well.water_depth_ft !== undefined && (
          <Row label="Water Depth" value={`${well.water_depth_ft.toLocaleString()} ft`} />
        )}
        {well.well_type && (
          <Row label="Type" value={well.well_type.replace("-", "/")} />
        )}
        <Row label="Operator" value={well.operator} />
        <Row label="County" value={`${well.county}, ${well.state}`} />
        <Row label="Spud Date" value={well.spud_date || "Unknown"} />
        <Row label="Status" value={well.status} />
      </div>
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-gray-500 text-xs">{label}</span>
      <span className={`text-xs font-medium ${highlight ? "text-amber-400" : "text-gray-200"}`}>{value}</span>
    </div>
  );
}
