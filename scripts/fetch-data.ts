/**
 * Downloads public oil/gas datasets from government sources.
 * Run: npx tsx scripts/fetch-data.ts
 *
 * Sources:
 *   - EIA shale plays: https://atlas.eia.gov/datasets/eia::tight-oil-and-shale-gas-plays-lower-48-states/explore
 *   - USGS National Oil and Gas Assessment: https://www.usgs.gov/programs/energy-resources-program/science/oil-and-gas-assessment
 *   - Texas RRC well data: https://www.rrc.texas.gov/resource-center/research/data-sets-available-for-download/
 *   - EIA production: https://www.eia.gov/petroleum/production/
 *
 * This script is a placeholder. The actual download steps depend on which
 * format/endpoint you grab from each source (most are bulk downloads, not APIs).
 *
 * Recommended approach:
 *   1. Download EIA plays GeoJSON from the ArcGIS Hub link above → save to data/raw/plays.geojson
 *   2. Download USGS assessment shapefile → convert with ogr2ogr → data/raw/assessment.geojson
 *   3. Download Texas RRC "Oil Well" CSV → data/raw/wells-tx.csv
 *   4. Download EIA monthly production CSV → data/raw/production.csv
 *   5. Run scripts/preprocess.ts to clean and copy to public/data/
 */

import * as fs from "fs";
import * as path from "path";

const RAW_DIR = path.join(process.cwd(), "data/raw");
const PUBLIC_DIR = path.join(process.cwd(), "public/data");

function ensureDirs() {
  [RAW_DIR, PUBLIC_DIR].forEach((d) => {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  });
}

function writeSampleData() {
  // Minimal sample data so the app renders without real downloads
  const playsPath = path.join(PUBLIC_DIR, "plays.geojson");
  if (!fs.existsSync(playsPath)) {
    const samplePlays = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: { name: "Permian Basin" },
          geometry: {
            type: "Polygon",
            coordinates: [[
              [-104, 28], [-100, 28], [-100, 33], [-104, 33], [-104, 28]
            ]]
          }
        },
        {
          type: "Feature",
          properties: { name: "Bakken" },
          geometry: {
            type: "Polygon",
            coordinates: [[
              [-105, 46], [-99, 46], [-99, 49], [-105, 49], [-105, 46]
            ]]
          }
        },
        {
          type: "Feature",
          properties: { name: "Eagle Ford" },
          geometry: {
            type: "Polygon",
            coordinates: [[
              [-101, 27], [-97, 27], [-97, 30], [-101, 30], [-101, 27]
            ]]
          }
        },
        {
          type: "Feature",
          properties: { name: "DJ Basin" },
          geometry: {
            type: "Polygon",
            coordinates: [[
              [-106, 39], [-103, 39], [-103, 41], [-106, 41], [-106, 39]
            ]]
          }
        },
      ]
    };
    fs.writeFileSync(playsPath, JSON.stringify(samplePlays, null, 2));
    console.log("Wrote sample plays.geojson");
  }

  const wellsPath = path.join(PUBLIC_DIR, "wells.json");
  if (!fs.existsSync(wellsPath)) {
    // A few sample wells around the Permian Basin
    const sampleWells = [
      { id: "w1", lat: 31.8, lon: -102.3, depth_ft: 8500, operator: "Pioneer Natural Resources", spud_date: "2022-03-15", status: "Active", county: "Midland", state: "TX" },
      { id: "w2", lat: 31.6, lon: -102.8, depth_ft: 12000, operator: "Occidental Petroleum", spud_date: "2021-07-20", status: "Active", county: "Ector", state: "TX" },
      { id: "w3", lat: 32.1, lon: -101.9, depth_ft: 9200, operator: "ConocoPhillips", spud_date: "2023-01-05", status: "Active", county: "Andrews", state: "TX" },
      { id: "w4", lat: 31.4, lon: -103.1, depth_ft: 14500, operator: "ExxonMobil", spud_date: "2020-11-12", status: "Inactive", county: "Winkler", state: "TX" },
      { id: "w5", lat: 31.9, lon: -102.1, depth_ft: 7800, operator: "Devon Energy", spud_date: "2023-06-18", status: "Active", county: "Midland", state: "TX" },
    ];
    fs.writeFileSync(wellsPath, JSON.stringify(sampleWells, null, 2));
    console.log("Wrote sample wells.json");
  }
}

ensureDirs();
writeSampleData();
console.log("\nSample data written to public/data/");
console.log("Replace with real data by downloading from the sources listed at the top of this file.");
