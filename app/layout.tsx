import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const BASE_URL = "https://oil-map-git-main-andrews-projects-212d71a8.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "US Oil Map — 4.4M wells across 50 states",
    template: "%s · US Oil Map",
  },
  description:
    "Interactive map of 4.4 million oil, gas, and water wells across all 50 US states and federal offshore. Filter by status, toggle 3D depth columns, and explore shale plays and production data.",
  keywords: ["oil map", "gas wells", "US oil production", "shale plays", "Permian Basin", "Marcellus", "well data", "oil and gas"],
  authors: [{ name: "Andrew Shubitowski", url: "https://github.com/ashubitowski" }],
  openGraph: {
    type: "website",
    siteName: "US Oil Map",
    title: "US Oil Map — 4.4M wells across 50 states",
    description:
      "Interactive map of 4.4 million oil, gas, and water wells across all 50 US states. Explore shale plays, production data, and per-well depth.",
    url: BASE_URL,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "US Oil Map" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "US Oil Map — 4.4M wells across 50 states",
    description:
      "Interactive map of 4.4 million oil, gas, and water wells across all 50 US states.",
    images: ["/opengraph-image"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-full bg-gray-950">
        {children}
        <Analytics />
      </body>
    </html>
  );
}
