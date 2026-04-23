import type { MetadataRoute } from "next";

const BASE_URL = "https://oil-map-git-main-andrews-projects-212d71a8.vercel.app";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${BASE_URL}/sitemap.xml`,
  };
}
