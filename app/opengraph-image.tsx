import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "US Oil Map — 4.4 million wells across all 50 states";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          background: "#030712",
          padding: "80px 96px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {/* Amber accent bar */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 4,
            background: "#f59e0b",
          }}
        />

        {/* Derrick mark */}
        <svg
          width="64"
          height="64"
          viewBox="0 0 32 32"
          fill="none"
          style={{ marginBottom: 32 }}
        >
          <line x1="16" y1="4" x2="6" y2="28" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" />
          <line x1="16" y1="4" x2="26" y2="28" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" />
          <line x1="9" y1="19" x2="23" y2="19" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
          <line x1="5" y1="28" x2="27" y2="28" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="16" cy="4" r="2.5" fill="#f59e0b" />
        </svg>

        {/* Title */}
        <div
          style={{
            fontSize: 72,
            fontWeight: 700,
            color: "#ffffff",
            lineHeight: 1.05,
            letterSpacing: "-2px",
            marginBottom: 24,
          }}
        >
          US Oil Map
        </div>

        {/* Stats line */}
        <div
          style={{
            fontSize: 28,
            color: "#6b7280",
            fontWeight: 400,
            letterSpacing: "-0.5px",
            marginBottom: 48,
          }}
        >
          4,406,261 wells &nbsp;·&nbsp; 50 states &nbsp;·&nbsp; Federal offshore
        </div>

        {/* Tags */}
        <div style={{ display: "flex", gap: 12 }}>
          {["Wells", "Shale Plays", "Oil Probability", "Production"].map((tag) => (
            <div
              key={tag}
              style={{
                background: "#111827",
                border: "1px solid #374151",
                borderRadius: 9999,
                padding: "8px 18px",
                fontSize: 16,
                color: "#9ca3af",
              }}
            >
              {tag}
            </div>
          ))}
        </div>

        {/* Bottom byline */}
        <div
          style={{
            position: "absolute",
            bottom: 48,
            right: 96,
            fontSize: 18,
            color: "#374151",
          }}
        >
          Built by Andrew Shubitowski
        </div>
      </div>
    ),
    { ...size }
  );
}
