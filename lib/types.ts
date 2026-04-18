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
  source?: "synthetic" | "rrc" | "boem";
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

export type LayerId = "plays" | "wells" | "probability" | "production" | "wells3d";

export interface LayerState {
  plays: boolean;
  wells: boolean;
  probability: boolean;
  production: boolean;
  wells3d: boolean;
}

export interface ProductionHistoryEntry {
  month: string;
  bpd: number;
}

export type ProductionHistory = Record<string, ProductionHistoryEntry[]>;
