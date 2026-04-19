"use client";

import { useState } from "react";

interface Props {
  errors: Record<string, string>;
  loading?: string[];
}

export default function LoadBanner({ errors, loading = [] }: Props) {
  const [dismissed, setDismissed] = useState(false);
  const entries = Object.entries(errors);
  const hasErrors = entries.length > 0 && !dismissed;
  const hasLoading = loading.length > 0;

  if (!hasErrors && !hasLoading) return null;

  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex flex-col gap-1.5 items-center">
      {hasLoading && (
        <div className="bg-gray-900/90 border border-gray-700 rounded-lg px-3 py-1.5 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse flex-shrink-0" />
          <p className="text-xs text-gray-300">
            Loading wells for {loading.join(", ")}…
          </p>
        </div>
      )}
      {hasErrors && (
        <div className="bg-gray-900/95 border border-red-800 rounded-lg px-3 py-2 flex items-start gap-3 max-w-sm">
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
      )}
    </div>
  );
}
