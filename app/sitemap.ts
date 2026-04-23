import type { MetadataRoute } from "next";

const BASE_URL = "https://oil-map-git-main-andrews-projects-212d71a8.vercel.app";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
