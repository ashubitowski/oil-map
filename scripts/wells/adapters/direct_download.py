"""
Pattern A: Direct bulk download — ZIP or plain CSV over HTTPS.

Handles:
- ZIP containing a CSV/text/DBF file (ND, CO, BOEM)
- Plain CSV download (KS, WY)
Auto-detects delimiter (comma, tab, pipe).
"""

import csv
import io
import sys
import zipfile
from pathlib import Path
from typing import Iterator

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

from scripts.wells.adapters.base import Adapter, BaseConfig


class DirectDownloadAdapter(Adapter):
    """
    Downloads a single file (ZIP or CSV) and iterates CSV rows.
    Override parse() in subclasses that need multiple files or non-CSV formats.
    """

    def download(self) -> Path:
        cfg = self.config
        filename = cfg.raw_filename or Path(cfg.url.split("?")[0]).name or "download"
        raw_file = cfg.raw_dir / filename
        if raw_file.exists():
            print(f"  Using cached {raw_file} (delete to re-download)")
            return raw_file
        print(f"  Downloading {cfg.url} ...")
        resp = requests.get(cfg.url, timeout=180, stream=True)
        resp.raise_for_status()
        total = 0
        with open(raw_file, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
                total += len(chunk)
        print(f"  Saved {total / 1e6:.1f} MB → {raw_file}")
        return raw_file

    def parse(self, raw: Path) -> Iterator[dict]:
        if raw.suffix.lower() == ".zip":
            yield from self._parse_zip(raw)
        else:
            yield from self._parse_csv_file(raw)

    def _parse_zip(self, zip_path: Path) -> Iterator[dict]:
        with zipfile.ZipFile(zip_path) as zf:
            candidates = [n for n in zf.namelist()
                          if n.lower().endswith((".csv", ".txt", ".dat"))]
            dbfs = [n for n in zf.namelist() if n.lower().endswith(".dbf")]
            names = candidates or dbfs
            if not names:
                raise RuntimeError(f"No data file in ZIP {zip_path}. Contents: {zf.namelist()}")
            data_file = names[0]
            print(f"  Parsing {data_file} from ZIP ...")
            with zf.open(data_file) as f:
                raw_text = f.read().decode("utf-8", errors="replace")
        yield from self._iter_csv(raw_text)

    def _parse_csv_file(self, path: Path) -> Iterator[dict]:
        # utf-8-sig strips BOM if present (common in ArcGIS Hub CSV exports)
        raw_text = path.read_text(encoding="utf-8-sig", errors="replace")
        yield from self._iter_csv(raw_text)

    def _iter_csv(self, text: str) -> Iterator[dict]:
        sample = text[:2000]
        delimiter = "\t" if "\t" in sample else ("|" if "|" in sample else ",")
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        headers = [h.strip().upper() for h in (reader.fieldnames or [])]
        print(f"  Columns ({len(headers)}): {', '.join(headers[:12])} ...")
        yield from reader
