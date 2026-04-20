export interface Well {
  id: string;
  lat: number;
  lon: number;
  depth_ft: number;
  operator: string;
  spud_date: string;
  status: string;
  county: string;
  state: string;
  water_depth_ft?: number;
  source?: "synthetic" | "rrc" | "boem" | "nd-ogic" | "co-ecmc" | "ks-kgs" | "wy-wogcc" | "nm-ocd" | "ca-calgem" | "ok-occ";
  well_type?: "oil" | "gas" | "oil-gas" | "injection" | "disposal" | "other";
}

export interface Play {
  name: string;
  type: "oil" | "gas" | "both";
  basin: string;
}

export interface AssessmentUnit {
  name: string;
  unit_id: string;
  probability: number; // 0-1
  mean_bbo: number; // billion barrels of oil
}

export interface ProductionBasin {
  id: string;
  name: string;
  lon: number;
  lat: number;
  states: string[];
  color: string;
  bpd: number;
  month: string; // YYYY-MM
}

export interface WellManifestEntry {
  file: string;
  bbox: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  count: number;
  category?: "oil-gas" | "water-other"; // omitted = oil-gas
}

export interface WellManifest {
  version: number;
  states: Record<string, WellManifestEntry>;
}

export type WellStatus = "Active" | "Inactive" | "Plugged & Abandoned" | "Permitted" | "Unknown";
export const WELL_STATUSES: WellStatus[] = ["Active", "Inactive", "Plugged & Abandoned", "Permitted", "Unknown"];

export type LayerId = "plays" | "wells" | "probability" | "production" | "wells3d" | "waterWells";

export interface LayerState {
  plays: boolean;
  wells: boolean;
  probability: boolean;
  production: boolean;
  wells3d: boolean;
  waterWells: boolean;
}

export interface ProductionHistoryEntry {
  month: string;
  bpd: number;
}

export type ProductionHistory = Record<string, ProductionHistoryEntry[]>;
