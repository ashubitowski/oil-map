"use client";

import { Well } from "@/lib/types";

interface Props {
  well: Well;
  onClose: () => void;
}

const SOURCE_LABELS: Record<string, string> = {
  synthetic:     "Synthetic",
  rrc:           "TX Railroad Commission",
  boem:          "BOEM OCS",
  "nd-ogic":     "ND Oil & Gas Division",
  "co-ecmc":     "CO ECMC",
  "ks-kgs":      "KS Geological Survey",
  "wy-wogcc":    "WY Oil & Gas Commission",
  "nm-ocd":      "NM Oil Conservation Division",
  "ca-calgem":   "CA CalGEM",
  "ok-occ":      "OK Corporation Commission",
  "pa-dep":      "PA Dept. of Environmental Protection",
  "mt-bogc":     "MT Board of Oil & Gas",
  "ut-dogm":     "UT Div. of Oil, Gas & Mining",
  "wv-dep":      "WV Dept. of Environmental Protection",
  "oh-odnr":     "OH Div. of Natural Resources",
  "la-sonris":   "LA SONRIS",
  "il-isgs":     "IL State Geological Survey",
  "mi-egle":     "MI EGLE",
  "ar-aogc":     "AR Oil & Gas Commission",
  "ms-ogb":      "MS Oil & Gas Board",
  "ak-aogcc":    "AK Oil & Gas Conservation Commission",
  "al-ogb":      "AL Oil & Gas Board",
  "ny-dec":      "NY Dept. of Environmental Conservation",
  "ky-kgs":      "KY Geological Survey",
  "ne-nogcc":    "NE Oil & Gas Conservation Commission",
  "fl-dep":      "FL Dept. of Environmental Protection",
  "va-energy":   "VA Dept. of Energy",
  "tn-deg":      "TN Div. of Geology",
  "in-dnr":      "IN Dept. of Natural Resources",
  "nv-minerals": "NV Div. of Minerals",
  "sd-denr":     "SD Dept. of Agriculture & Natural Resources",
  "md-dnr":      "MD Dept. of Natural Resources",
  "id-idl":      "ID Dept. of Lands",
  "mn-dnr":      "MN Dept. of Natural Resources",
  "wa-dnr":      "WA Dept. of Natural Resources",
  "nc-deq":      "NC Dept. of Environmental Quality",
  "az-aogcc":    "AZ Oil & Gas Conservation Commission",
  "or-dogami":   "OR Dept. of Geology & Mineral Industries",
  "nj-dep":      "NJ Dept. of Environmental Protection",
  "ia-dnr":      "IA Dept. of Natural Resources",
  "mo-dnr":      "MO Dept. of Natural Resources",
  "ga-epd":      "GA Environmental Protection Division",
  "me-mgs":      "ME Geological Survey",
  "nh-granit":   "NH GRANIT / Well Completion Reports",
  "hi-dlnr":     "HI DLNR / USGS NWIS",
  "vt-vgs":      "VT Agency of Natural Resources",
  "ri-dem":      "RI Dept. of Environmental Management",
  "ct-deep":     "CT Dept. of Consumer Protection",
  "sc-dnr":      "SC Dept. of Natural Resources",
  "ma-mgs":      "MA Geological Survey",
  "wi-dnr":      "WI Dept. of Natural Resources",
  "de-dnrec":    "DE Dept. of Natural Resources",
};

export default function WellPopup({ well, onClose }: Props) {
  const sourceLabel = well.source ? (SOURCE_LABELS[well.source] ?? well.source) : null;

  return (
    <div className="absolute top-20 left-4 z-20 bg-gray-950/95 border border-gray-800 rounded-lg p-4 min-w-[220px] backdrop-blur-sm shadow-xl">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">Well</p>
          {sourceLabel && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-500 border border-gray-700/60">
              {sourceLabel}
            </span>
          )}
        </div>
        <button onClick={onClose} className="text-gray-600 hover:text-gray-300 text-sm leading-none ml-2 flex-shrink-0">✕</button>
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
