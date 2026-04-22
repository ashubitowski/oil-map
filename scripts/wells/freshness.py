"""
Generate wells-freshness.json: latest scrape date per state.
Reads all public/data/wells-*.meta.json files and emits a compact bundle
that the frontend Attribution component uses to display "Updated {date}".

Usage: python3 scripts/wells/freshness.py
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "public" / "data"
OUT = DATA_DIR / "wells-freshness.json"


def main() -> None:
    states: dict[str, str] = {}
    for path in DATA_DIR.glob("wells-*.meta.json"):
        try:
            meta = json.loads(path.read_text())
            state = meta.get("state", "")
            date = meta.get("fetched_at", "")
            if state and date:
                states[state] = date
        except Exception:
            continue

    latest = max(states.values()) if states else ""
    result = {"latest": latest, "states": dict(sorted(states.items()))}
    OUT.write_text(json.dumps(result, indent=2))
    print(f"Wrote {OUT} — {len(states)} states, latest: {latest}")


if __name__ == "__main__":
    main()
