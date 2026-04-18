"""
CLI entry point for the wells fetcher framework.

Usage:
  python3 -m scripts.wells.fetch ND
  python3 -m scripts.wells.fetch ND --force       # delete cache, re-download
  python3 -m scripts.wells.fetch ND --dry-run     # parse + report, don't write
  python3 -m scripts.wells.fetch --list           # show registered states
  python3 -m scripts.wells.fetch ALL              # run every registered state

Run from the repo root (oil-map/).
"""

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path when invoked as `python3 -m scripts.wells.fetch`
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.wells.registry import REGISTRY


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch real well data for a US state.",
        epilog="Example: python3 -m scripts.wells.fetch ND",
    )
    parser.add_argument(
        "state",
        nargs="?",
        metavar="STATE",
        help="State code (ND, CO, KS, WY, NM, CA, OFFSHORE) or ALL",
    )
    parser.add_argument(
        "--list", action="store_true", help="List all registered states and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Download + parse but do not write output files",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Delete cached raw files and re-download",
    )
    args = parser.parse_args()

    if args.list:
        print("Registered states:")
        for code, adapter in sorted(REGISTRY.items()):
            cfg = adapter.config
            print(f"  {code:12s} → {cfg.output}  ({cfg.source_label})")
        return

    if not args.state:
        parser.print_help()
        sys.exit(1)

    targets = sorted(REGISTRY.keys()) if args.state.upper() == "ALL" else [args.state.upper()]

    for code in targets:
        if code not in REGISTRY:
            print(f"Unknown state '{code}'. Use --list to see available states.", file=sys.stderr)
            sys.exit(1)
        adapter = REGISTRY[code]
        cfg = adapter.config
        print(f"\n{'='*60}")
        print(f"Fetching {code} ({cfg.source_label})")
        print(f"  URL:    {cfg.url}")
        print(f"  Output: {cfg.output}")
        print(f"  Bounds: {cfg.bounds}")
        print(f"{'='*60}")

        if args.force:
            import shutil
            if cfg.raw_dir.exists():
                shutil.rmtree(cfg.raw_dir)
                print(f"  Cleared cache: {cfg.raw_dir}")

        try:
            wells = adapter.run(dry_run=args.dry_run, force=args.force)
            if args.dry_run:
                print(f"\n[dry-run] Would write {len(wells):,} wells to {cfg.output}")
        except Exception as e:
            print(f"\nERROR fetching {code}: {e}", file=sys.stderr)
            if len(targets) == 1:
                sys.exit(1)
            else:
                print("  Continuing with next state...")


if __name__ == "__main__":
    main()
