import datetime
import json
import threading

from . import config


class AvailabilityCache:
    """
    One row list, shared by every request — visitors read this, they never
    trigger a live upstream fetch themselves. Persisted to disk on every
    update so a container restart doesn't show an empty page until the next
    scheduled refresh completes.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._rows: dict[str, dict] = {}
        self.last_updated: str | None = None
        self._load()

    def _load(self):
        if not config.CACHE_FILE.exists():
            return
        try:
            raw = json.loads(config.CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        self._rows = raw.get("rows", {})
        self.last_updated = raw.get("last_updated")

    def _save(self):
        config.CACHE_FILE.write_text(json.dumps({
            "rows": self._rows,
            "last_updated": self.last_updated,
        }, ensure_ascii=False), encoding="utf-8")

    def set_rows(self, rows: dict[str, dict]):
        with self._lock:
            self._rows = rows
            self.last_updated = datetime.datetime.now().isoformat(timespec="seconds")
            self._save()

    def get_rows(self) -> list[dict]:
        with self._lock:
            return list(self._rows.values())


CACHE = AvailabilityCache()
