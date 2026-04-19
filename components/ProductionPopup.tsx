"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceDot } from "recharts";
import type { ProductionHistoryEntry } from "@/lib/types";

interface Basin {
  name: string;
  bpd: number;
  month: string;
  states: string[];
}

interface Props {
  basin: Basin;
  history?: ProductionHistoryEntry[];
  selectedMonth?: string;
  onClose: () => void;
}

function formatBpd(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M bbl/d`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K bbl/d`;
  return `${n.toLocaleString()} bbl/d`;
}

function SparkTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ProductionHistoryEntry }> }) {
  if (!active || !payload?.length) return null;
  const { month, bpd } = payload[0].payload;
  const label = new Date(month + "-01").toLocaleDateString("en-US", { month: "short", year: "numeric" });
  return (
    <div style={{ background: "#111827", border: "1px solid #374151", borderRadius: 4, padding: "4px 8px", fontSize: 10 }}>
      <div style={{ color: "#9ca3af" }}>{label}</div>
      <div style={{ color: "#ef4444", fontWeight: 500 }}>{formatBpd(bpd)}</div>
    </div>
  );
}

export default function ProductionPopup({ basin, history, selectedMonth, onClose }: Props) {
  const activeMonth = selectedMonth ?? basin.month;
  const monthLabel = new Date(activeMonth + "-01").toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const activeBpd = history?.find((e) => e.month === activeMonth)?.bpd ?? basin.bpd;
  const refEntry = history?.find((e) => e.month === activeMonth);

  return (
    <div className="absolute top-20 left-4 z-20 bg-gray-900/95 border border-gray-700 rounded-lg p-4 min-w-[220px]">
      <div className="flex justify-between items-start mb-3">
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">Production</p>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-sm leading-none">✕</button>
      </div>
      <div className="space-y-1.5">
        <div className="text-white font-semibold text-sm mb-2">{basin.name}</div>
        <Row label="Output" value={formatBpd(activeBpd)} highlight />
        <Row label="As of" value={monthLabel} />
        <Row label="States" value={basin.states.join(", ")} />
      </div>
      {history && (
        <div className="mt-3 border-t border-gray-700 pt-3">
          <p className="text-xs text-gray-500 mb-1.5">3-Year Trend</p>
          <LineChart width={188} height={48} data={history}>
            <XAxis dataKey="month" hide />
            <YAxis hide domain={["auto", "auto"]} />
            <Line
              type="monotone"
              dataKey="bpd"
              stroke="#ef4444"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
            <Tooltip content={<SparkTooltip />} />
            {refEntry && (
              <ReferenceDot x={activeMonth} y={refEntry.bpd} r={3} fill="#fbbf24" stroke="none" />
            )}
          </LineChart>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-gray-500 text-xs">{label}</span>
      <span className={`text-xs font-medium ${highlight ? "text-red-400" : "text-gray-200"}`}>{value}</span>
    </div>
  );
}
