"use client";

import { useState, useEffect, useRef } from "react";

interface Props {
  months: string[];
  selectedMonth: string;
  onChange: (month: string) => void;
}

export default function TimelineSlider({ months, selectedMonth, onChange }: Props) {
  const [playing, setPlaying] = useState(false);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const selectedMonthRef = useRef(selectedMonth);
  selectedMonthRef.current = selectedMonth;
  const monthsRef = useRef(months);
  monthsRef.current = months;

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      const ms = monthsRef.current;
      const idx = ms.indexOf(selectedMonthRef.current);
      if (idx >= ms.length - 1) {
        setPlaying(false);
        return;
      }
      onChangeRef.current(ms[idx + 1]);
    }, 500);
    return () => clearInterval(id);
  }, [playing]);

  const currentIndex = Math.max(0, months.indexOf(selectedMonth));
  const label = selectedMonth
    ? new Date(selectedMonth + "-01").toLocaleDateString("en-US", { month: "short", year: "numeric" })
    : "";

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 bg-gray-900/95 border border-gray-700 rounded-lg px-4 py-3 flex items-center gap-3 min-w-[320px]">
      <button
        onClick={() => {
          if (currentIndex >= months.length - 1) onChange(months[0]);
          setPlaying((p) => !p);
        }}
        className="text-gray-300 hover:text-white text-base w-5 text-center leading-none"
        title={playing ? "Pause" : "Play"}
      >
        {playing ? "⏸" : "▶"}
      </button>
      <input
        type="range"
        min={0}
        max={months.length - 1}
        value={currentIndex}
        onChange={(e) => {
          setPlaying(false);
          onChange(months[Number(e.target.value)]);
        }}
        aria-label="Timeline month"
        className="flex-1 accent-red-500"
      />
      <span className="text-xs text-gray-300 w-20 text-right tabular-nums">{label}</span>
    </div>
  );
}
