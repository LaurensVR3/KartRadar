import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

TRACKS_FILE = BASE_DIR / "tracks.yaml"
CATALOG_FILE = DATA_DIR / "centers_catalog.json"
CACHE_FILE = DATA_DIR / "availability_cache.json"

# Hour of day (local time, 0-23) for the once-daily full refresh: rebuilds
# the catalog (re-probes every Apex Timing center ID, re-applies the
# kart-vs-not-kart filter) and re-checks availability for every track.
# Default 0 = midnight.
DAILY_REFRESH_HOUR = int(os.environ.get("DAILY_REFRESH_HOUR", "0"))

DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", "28"))


def load_tracks() -> list[dict]:
    with open(TRACKS_FILE, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    return doc.get("tracks", [])
