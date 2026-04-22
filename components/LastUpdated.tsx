"use client";

import { useEffect, useState } from "react";
import { loadJSON } from "@/lib/data-loader";

export default function LastUpdated() {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    loadJSON<{ latest: string }>("/data/wells-freshness.json?v=1")
      .then((d) => {
        const date = new Date(d.latest + "T00:00:00");
        setLabel(date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }));
      })
      .catch(() => {});
  }, []);

  if (!label) return null;

  return (
    <span className="text-gray-600 text-xs hidden sm:block">
      Updated {label}
    </span>
  );
}
