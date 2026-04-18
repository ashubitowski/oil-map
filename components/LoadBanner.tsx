"use client";

import { useState } from "react";

interface Props {
  errors: Record<string, string>;
}

export default function LoadBanner({ errors }: Props) {
  const [dismissed, setDismissed] = useState(false);
  const entries = Object.entries(errors);
  if (entries.length === 0 || dismissed) return null;

  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 bg-gray-900/95 border border-red-800 rounded-lg px-3 py-2 flex items-start gap-3 max-w-sm">
      <div className="flex-1 space-y-0.5">
        {entries.map(([layer, msg]) => (
          <p key={layer} className="text-xs text-red-400">
            <span className="font-medium capitalize">{layer}</span>{" "}
            <span className="text-red-500/80">{msg}</span>
          </p>
        ))}
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-gray-600 hover:text-gray-400 text-sm leading-none flex-shrink-0 mt-0.5"
        aria-label="Dismiss error banner"
      >
        ✕
      </button>
    </div>
  );
}
