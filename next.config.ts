import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      // Broad rule: all /data/* files get a 1-hour cache
      {
        source: "/data/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=3600" }],
      },
      // Manifest is short-cached so new deploys propagate within 60s
      {
        source: "/data/wells-manifest.json",
        headers: [{ key: "Cache-Control", value: "public, max-age=60, must-revalidate" }],
      },
    ];
  },
};

export default nextConfig;
