import type { MetadataRoute } from "next";

const BASE_URL = "https://oil-map.vercel.app";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: `${BASE_URL}/`,
      lastModified: "2026-04-22",
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
