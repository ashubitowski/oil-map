# Wells Fetcher Framework

Replaces the per-state bespoke scripts (`fetch-wells-nd.py`, `fetch-wells-co.py`, etc.) with a config-driven framework. Each state is one Python file; no new adapter code needed for most sources.

## Usage

```bash
# From the oil-map/ repo root
python3 -m scripts.wells.fetch --list            # see all registered states
python3 -m scripts.wells.fetch ND               # fetch North Dakota
python3 -m scripts.wells.fetch CO --force       # re-download (ignore cache)
python3 -m scripts.wells.fetch NM --dry-run     # parse + report, no file write
python3 -m scripts.wells.fetch ALL              # run every state
```

Output files land in `public/data/wells-<state>.json` + a `.meta.json` sidecar.

Raw source files are cached in `data/raw/<state>/` (gitignored). Delete the directory to force a re-download.

## How to add a new state

1. **Find the source** — look for a bulk CSV/ZIP or ArcGIS FeatureServer URL from the state oil and gas commission.

2. **Create `scripts/wells/states/<abbr>.py`** — pick the right adapter:
   - `DirectDownloadAdapter` — ZIP or CSV download (most states)
   - `ArcGISAdapter` — ArcGIS REST FeatureServer (NM, CA, LA, etc.)
   - Subclass either one if you need custom logic (see `co.py` for a two-file join example)

3. **Instantiate `BaseConfig`** with:
   - `state` — two-letter code
   - `source_label` — added to `Well.source` in the JSON
   - `url` — primary download URL
   - `bounds` — `(S, N, W, E)` in decimal degrees for sanity filtering
   - `output` — `Path("public/data/wells-<abbr>.json")`
   - `raw_dir` — `Path("data/raw/<abbr>")`
   - `field_map` — canonical name → list of possible column names in the source
   - `status_map` / `well_type_map` — source code → canonical value

4. **Register it** in `scripts/wells/registry.py`.

5. **Verify**:
   ```bash
   python3 -m scripts.wells.fetch <ABBR> --dry-run
   ```
   Expected output: well count in the right ballpark, depth range makes geological sense, known basin cluster visible on map reload.

6. **Update frontend** — add the new file to the `WELL_MANIFEST` in `components/Map.tsx` and add `source_label` to `Well.source` in `lib/types.ts` and `SOURCE_LABELS` in `WellPopup.tsx`.

## Canonical field names

| Canonical | Description |
|---|---|
| `lat` | Surface latitude (WGS84 decimal degrees) |
| `lon` | Surface longitude (WGS84 decimal degrees) |
| `depth_ft` | Total measured depth in feet |
| `api` | API well number (10-digit normalized) |
| `operator` | Current operating company |
| `status` | Well status string |
| `well_type` | `oil`, `gas`, `oil-gas`, `injection`, `disposal`, `other` |
| `county` | County name (string, not FIPS) |
| `spud_date` | Spud date as ISO YYYY-MM-DD |

## Access patterns

| Pattern | Adapter | States |
|---|---|---|
| A. Direct bulk download | `DirectDownloadAdapter` | KS, WY, ND, OH, MI, AR, IN, KY, NE, NY |
| B. ArcGIS REST FeatureServer | `ArcGISAdapter` | NM, CA, LA, TN, VA |
| C. Query form / Playwright | custom (TBD) | TX (existing), OK, MT, AL, MS |
| D. Federal/offshore bulk | `BOEMAdapter` (subclass of A) | BOEM GOM |

## Payload check

After adding states, run:
```bash
du -sh public/data/wells-*.json
gzip -c public/data/wells-*.json | wc -c
```

Threshold: < 6 MB gzipped → ship as JSON. > 15 MB → convert to PMTiles (see plan).

## Dependencies

```bash
pip install requests
```

`pyshp` (`pip install pyshp`) needed if a state's raw source is a shapefile with no CSV equivalent.
