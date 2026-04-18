/**
 * Scrapes Texas RRC well data from the RRC Oil & Gas Public Research portal.
 *
 * Strategy:
 * 1. First run: opens headful Chromium so you can solve any CAPTCHA / accept terms.
 *    State (cookies, localStorage) is saved to scripts/.rrc-state.json.
 * 2. Subsequent runs: headless, restores saved state.
 * 3. Iterates through all 9 RRC oil/gas districts.
 * 4. Checkpoints progress to data/raw/rrc/checkpoint.json — interrupted runs resume.
 * 5. Outputs public/data/wells-tx.json in the Well shape.
 *
 * Usage:
 *   npm run scrape:rrc
 *   npm run scrape:rrc -- --reset    (clear session state and start fresh)
 *
 * NOTE: This scraper targets the RRC public well query interface.
 * It will break if RRC redesigns their portal — that's expected and fine for a
 * personal project. Check https://www.rrc.texas.gov if selectors stop working.
 *
 * RRC well query portal: https://www.rrc.texas.gov/oil-gas/research-and-statistics/well-information/statewide-queries/
 */

import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import * as fs from "fs";
import * as path from "path";

const RRC_QUERY_URL = "https://www.rrc.texas.gov/oil-gas/research-and-statistics/well-information/statewide-queries/";
const RRC_BULK_BASE = "https://www.rrc.texas.gov/resource-center/research/data-sets-available-for-download/";
const STATE_FILE = path.join(__dirname, ".rrc-state.json");
const CHECKPOINT_FILE = path.join("data/raw/rrc/checkpoint.json");
const RAW_DIR = "data/raw/rrc";
const OUT_FILE = "public/data/wells-tx.json";

// RRC oil/gas districts 1–10 (no 6E distinction needed at this level)
const DISTRICTS = ["01", "02", "03", "04", "05", "06", "07B", "07C", "08", "08A", "09", "10"];

interface WellRecord {
  id: string;
  lat: number;
  lon: number;
  depth_ft: number;
  operator: string;
  spud_date: string;
  status: string;
  county: string;
  state: "TX";
  source: "rrc";
}

interface Checkpoint {
  completedDistricts: string[];
  wells: WellRecord[];
}

function loadCheckpoint(): Checkpoint {
  try {
    return JSON.parse(fs.readFileSync(CHECKPOINT_FILE, "utf-8"));
  } catch {
    return { completedDistricts: [], wells: [] };
  }
}

function saveCheckpoint(cp: Checkpoint) {
  fs.mkdirSync(RAW_DIR, { recursive: true });
  fs.writeFileSync(CHECKPOINT_FILE, JSON.stringify(cp, null, 2));
}

function loadState(): Record<string, unknown> | null {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf-8"));
  } catch {
    return null;
  }
}

function saveState(state: Record<string, unknown>) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

async function setupContext(browser: Browser, saved: Record<string, unknown> | null): Promise<BrowserContext> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ctx = await browser.newContext({
    storageState: saved as any,
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
  });
  return ctx;
}

/**
 * Navigate to the RRC query portal and accept any terms/CAPTCHA.
 * On first run (headful), waits for the user to handle any gate manually.
 */
async function ensurePortalAccess(page: Page, headful: boolean) {
  await page.goto(RRC_QUERY_URL, { waitUntil: "domcontentloaded", timeout: 30_000 });

  // Wait for main content — if terms/CAPTCHA appears the user handles it manually
  if (headful) {
    console.log("  >> Headful mode: handle any CAPTCHA or terms in the browser window, then press Enter here.");
    await new Promise<void>((resolve) => {
      process.stdin.once("data", () => resolve());
    });
  } else {
    // Try to detect a terms/agree button and click it
    const agreeBtn = page.locator('button:has-text("Agree"), button:has-text("Accept"), input[value="Agree"]').first();
    if (await agreeBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await agreeBtn.click();
      await page.waitForLoadState("domcontentloaded");
    }
  }
}

/**
 * Scrape wells for a single RRC district.
 * Returns array of raw well records scraped from the query results page.
 *
 * This targets the RRC statewide query form which has a district filter dropdown.
 * The exact selectors may need updating if RRC changes their UI.
 */
async function scrapeDistrict(page: Page, district: string): Promise<WellRecord[]> {
  console.log(`  Scraping district ${district}...`);

  // Navigate to the query page and select the district
  await page.goto(RRC_QUERY_URL, { waitUntil: "domcontentloaded", timeout: 30_000 });

  // Try to find and fill the district selector
  // These selectors are based on the RRC portal structure as of 2024 — may change
  try {
    const districtSelect = page.locator('select[name*="district" i], select[id*="district" i]').first();
    if (await districtSelect.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await districtSelect.selectOption({ label: district });
    }

    // Submit the query
    const submitBtn = page.locator('input[type="submit"], button[type="submit"]').first();
    if (await submitBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await submitBtn.click();
      await page.waitForLoadState("domcontentloaded", { timeout: 15_000 });
    }

    // Try to find an "Export to CSV" or download link
    const csvLink = page.locator('a:has-text("CSV"), a:has-text("Download"), a:has-text("Export")').first();
    if (await csvLink.isVisible({ timeout: 3_000 }).catch(() => false)) {
      const [download] = await Promise.all([
        page.waitForEvent("download", { timeout: 15_000 }),
        csvLink.click(),
      ]);
      const rawPath = path.join(RAW_DIR, `district_${district}.csv`);
      await download.saveAs(rawPath);
      return parseCsvToWells(rawPath, district);
    }

    // Fallback: parse table rows from the results page
    return await parseTableToWells(page, district);
  } catch (err) {
    console.warn(`    District ${district} scrape failed: ${err instanceof Error ? err.message : err}`);
    return [];
  }
}

function parseCsvToWells(csvPath: string, district: string): WellRecord[] {
  const text = fs.readFileSync(csvPath, "utf-8");
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  if (lines.length < 2) return [];

  const headers = lines[0].split(",").map((h) => h.toLowerCase().trim().replace(/"/g, ""));
  const idx = (names: string[]) => {
    for (const name of names) {
      const i = headers.findIndex((h) => h.includes(name));
      if (i >= 0) return i;
    }
    return -1;
  };

  const latIdx = idx(["latitude", "lat"]);
  const lonIdx = idx(["longitude", "lon"]);
  const depthIdx = idx(["total_depth", "total depth", "depth", "td_ft"]);
  const apiIdx = idx(["api", "api_number", "api_no"]);
  const operatorIdx = idx(["operator", "company"]);
  const spudIdx = idx(["spud", "spud_date"]);
  const statusIdx = idx(["status", "well_status"]);
  const countyIdx = idx(["county"]);

  const wells: WellRecord[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",").map((c) => c.trim().replace(/"/g, ""));
    const lat = latIdx >= 0 ? parseFloat(cols[latIdx]) : NaN;
    const lon = lonIdx >= 0 ? parseFloat(cols[lonIdx]) : NaN;
    const depth = depthIdx >= 0 ? parseFloat(cols[depthIdx]) : NaN;

    if (!isFinite(lat) || !isFinite(lon) || !isFinite(depth) || depth <= 0) continue;

    const api = apiIdx >= 0 ? cols[apiIdx] : "";
    const wellId = api || `rrc-${district}-${i}`;

    wells.push({
      id: wellId,
      lat: Math.round(lat * 1e6) / 1e6,
      lon: Math.round(lon * 1e6) / 1e6,
      depth_ft: Math.round(depth),
      operator: operatorIdx >= 0 ? cols[operatorIdx] : "Unknown",
      spud_date: spudIdx >= 0 ? cols[spudIdx] : "",
      status: statusIdx >= 0 ? cols[statusIdx] : "Unknown",
      county: countyIdx >= 0 ? cols[countyIdx] : "",
      state: "TX",
      source: "rrc",
    });
  }
  return wells;
}

async function parseTableToWells(page: Page, district: string): Promise<WellRecord[]> {
  // Fallback: try to read a results table from the page
  const rows = await page.$$eval("table tbody tr", (trs) =>
    trs.map((tr) => Array.from(tr.querySelectorAll("td")).map((td) => td.textContent?.trim() ?? ""))
  );

  const wells: WellRecord[] = [];
  for (const row of rows) {
    if (row.length < 5) continue;
    // Column order varies — this is a best-effort parse; adjust based on actual RRC table
    const lat = parseFloat(row[6] ?? "");
    const lon = parseFloat(row[7] ?? "");
    const depth = parseFloat(row[5] ?? "");
    if (!isFinite(lat) || !isFinite(lon) || !isFinite(depth)) continue;
    wells.push({
      id: row[0] || `rrc-${district}-${wells.length}`,
      lat,
      lon,
      depth_ft: Math.round(depth),
      operator: row[3] ?? "Unknown",
      spud_date: row[4] ?? "",
      status: row[2] ?? "Unknown",
      county: row[1] ?? "",
      state: "TX",
      source: "rrc",
    });
  }
  return wells;
}

async function main() {
  const reset = process.argv.includes("--reset");
  if (reset && fs.existsSync(STATE_FILE)) {
    fs.unlinkSync(STATE_FILE);
    console.log("Cleared session state.");
  }

  const savedState = loadState();
  const firstRun = !savedState;
  const headful = firstRun;

  if (firstRun) {
    console.log("First run — opening headful browser. Handle any CAPTCHA/terms, then press Enter.");
  }

  const checkpoint = loadCheckpoint();
  console.log(`Resuming from checkpoint: ${checkpoint.completedDistricts.length}/${DISTRICTS.length} districts done.`);

  const browser = await chromium.launch({ headless: !headful });
  const ctx = await setupContext(browser, savedState);
  const page = await ctx.newPage();

  try {
    await ensurePortalAccess(page, headful);

    // Save session state after portal access
    const state = await ctx.storageState();
    saveState(state as unknown as Record<string, unknown>);
    console.log("Session state saved.");

    for (const district of DISTRICTS) {
      if (checkpoint.completedDistricts.includes(district)) {
        console.log(`  District ${district}: already done (${
          checkpoint.wells.filter((w) => w.id.includes(district)).length
        } wells)`);
        continue;
      }

      // Rate limit: 1 district per 2 seconds minimum
      await page.waitForTimeout(2_000);

      const districtWells = await scrapeDistrict(page, district);
      console.log(`  District ${district}: ${districtWells.length} wells`);

      checkpoint.wells.push(...districtWells);
      checkpoint.completedDistricts.push(district);
      saveCheckpoint(checkpoint);
    }

    // Deduplicate by id
    const seen = new Set<string>();
    const dedupedWells = checkpoint.wells.filter((w) => {
      if (seen.has(w.id)) return false;
      seen.add(w.id);
      return true;
    });

    fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
    fs.writeFileSync(OUT_FILE, JSON.stringify(dedupedWells, null, 2));

    console.log(`\nWrote ${dedupedWells.length} TX wells to ${OUT_FILE}`);
    if (dedupedWells.length > 0) {
      const depths = dedupedWells.map((w) => w.depth_ft);
      console.log(`Depth range: ${Math.min(...depths).toLocaleString()} – ${Math.max(...depths).toLocaleString()} ft`);
    }
  } catch (err) {
    console.error("Scrape failed:", err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
