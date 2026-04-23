# US Oil Map

An interactive map of 4.4 million US oil, gas, and water wells built with Next.js, MapLibre GL, and deck.gl — all public data, no API keys required.

**Live:** [oil-map.vercel.app](https://oil-map.vercel.app)

## Layers

| Layer | Data Source | Description |
|---|---|---|
| Wells | 50 state agencies + [BOEM OCS](https://www.data.boem.gov/Main/Borehole.aspx) | 4.4M oil, gas, and water wells colored by depth |
| Shale Plays | [EIA](https://www.eia.gov/maps/maps.htm) | 50 major play polygons with hover labels; extruded in 3D mode |
| Oil Probability | [USGS NOGA](https://www.usgs.gov/programs/energy-resources-program/science/national-oil-and-gas-assessment) | 32 assessment unit polygons colored by probability of recoverable oil |
| Production | [EIA v2 API](https://api.eia.gov/v2/petroleum/crd/drill/data/) | Sized bubbles at major basin centroids, 36-month timeline slider |

## Features

- **4.4M wells across 50 states** — binary format (~30 bytes/well), loaded per-state as you pan
- **3D depth columns** — toggle 3D for deck.gl ColumnLayer extrusion by true well depth; cinematic flyTo camera, directional lighting with warm sun + cool rim, and specular material on all columns
- **National density view** — in 3D at low zoom, well density renders as towering columns across the US (deep formations like Permian and Haynesville visibly stand out)
- **Extruded shale plays** — plays rise as translucent amber 25km slabs alongside the well columns in 3D mode
- **Depth color ramp** — bright cyan (shallow) → blue → indigo → near-black (deep); wells with no depth data are hidden in 3D but visible in 2D
- **Timeline slider** — scrub through 3 years of production history; bubbles resize in real time
- **Sparkline popup** — click any production bubble for a 36-month trend chart
- **Shareable URLs** — layers, viewport, selected feature, and timeline month all encoded in the URL
- **Offshore wells** — BOEM Gulf of Mexico OCS wells with water depth in popup (cyan outline)
- **Water / monitoring well toggle** — 10 states (CT, DE, HI, MA, ME, NH, RI, SC, VT, WI) classified as water-other, off by default

## Stack

- [Next.js 16](https://nextjs.org/) (App Router, Turbopack)
- [MapLibre GL JS](https://maplibre.org/) — open-source map renderer, no API key
- [deck.gl 9](https://deck.gl/) — 3D ColumnLayer overlay with LightingEffect
- [Recharts](https://recharts.org/) — production trend sparklines
- [Tailwind CSS 4](https://tailwindcss.com/)
- [Cloudflare R2](https://www.cloudflare.com/developer-platform/r2/) — binary well data (zero egress cost)

## Running locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Well data is served from Cloudflare R2 via `NEXT_PUBLIC_DATA_BASE_URL`. For local dev without R2 access, place the binary files under `public/data/` (gitignored).

## Data pipeline

Python adapters in `scripts/wells/states/` normalize per-state source data into a shared binary format (WELL v2, ~30 bytes/well). Each state adapter outputs a `.bin` file and a `.meta.json` with source URL, fetch date, and well count.

```bash
# Run a specific state adapter (example: Texas via RRC)
python3 scripts/wells/states/tx.py

# Regenerate the manifest + overview after adding states
python3 scripts/wells/manifest.py
python3 scripts/wells/overview.py

# Regenerate the freshness summary (latest fetch date per state)
python3 scripts/wells/freshness.py

# Upload all data files to R2
sh scripts/upload-data.sh
```

Built by [Shuby](https://github.com/ashubitowski).

## License

MIT
