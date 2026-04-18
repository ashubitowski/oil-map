# US Oil Map

An interactive map of US oil and gas activity built with Next.js, MapLibre GL, and deck.gl — all public data, no API keys required.

**Live demo:** [oil-map.vercel.app](https://oil-map.vercel.app)

## Layers

| Layer | Data Source | Description |
|---|---|---|
| Shale Plays | [EIA](https://www.eia.gov/maps/maps.htm) | 50 major shale play polygons with hover labels |
| Wells + Depth | Synthetic (polygon-constrained) + [BOEM OCS](https://www.bsee.gov/tools-center/bsee-data-center) | ~1,800 onshore wells and Gulf of Mexico offshore wells colored by depth |
| Oil Probability | [USGS NOGA](https://www.usgs.gov/programs/energy-resources-program/science/national-oil-and-gas-assessment) | 32 assessment unit polygons colored by probability of recoverable oil |
| Production | [EIA Drilling Productivity Report](https://www.eia.gov/petroleum/drilling/) | Sized bubbles at 7 major basin centroids, 36-month timeline slider |

## Features

- **Timeline slider** — scrub through 3 years of production history (2021–2024); bubbles resize in real time
- **Sparkline popup** — click any production bubble for a 36-month trend chart
- **3D well columns** — toggle "3D depth columns" under Wells for deck.gl extrusion by depth
- **Shareable URLs** — layers, viewport, selected feature, and timeline month all encoded in the URL
- **Offshore wells** — BOEM Gulf of Mexico OCS wells with water depth in popup (cyan outline)

## Stack

- [Next.js 16](https://nextjs.org/) (App Router, Turbopack)
- [MapLibre GL JS](https://maplibre.org/) — open-source map renderer, no API key
- [deck.gl 9](https://deck.gl/) — 3D layer overlay
- [Recharts](https://recharts.org/) — production trend sparklines
- [Tailwind CSS 4](https://tailwindcss.com/)

## Running locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The preprocessed data files are committed to `public/data/` so the app works immediately with no setup.

## Regenerating data

Raw source files live in `data/raw/` (gitignored). Scripts output to `public/data/`.

```bash
# EIA shale plays (shapefile → GeoJSON)
# Download EIA shale plays shapefile to data/raw/ first
python3 scripts/fetch-data.ts

# USGS assessment units
python3 scripts/convert-usgs-au.py

# Synthetic onshore wells (polygon-constrained with realistic depth profiles)
python3 scripts/generate-wells.py

# EIA production data (requires data/raw/dpr-data.xlsx from EIA DPR page)
python3 scripts/generate-production.py

# BOEM Gulf of Mexico offshore wells
npm run generate:offshore

# Real Texas wells via RRC portal (Playwright — opens browser on first run)
npm run scrape:rrc
```

## License

MIT
