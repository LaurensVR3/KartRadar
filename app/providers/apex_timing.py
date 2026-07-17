"""
Apex Timing provider — two booking modes seen across tracks so far:
  "sessions": POST request_session_booking.php, returns {date: bool}
  "calendar": POST request_calendar.php per week, returns an HTML fragment
              with per-day status (used by tracks with no sessions_booking
              products for own-kart, e.g. Karting Genk).
See ../../catalog/build_catalog.py for how centers/products are discovered.
"""
import datetime
import json

import requests
from bs4 import BeautifulSoup

from .base import Provider

API_BASE = "https://www.apex-timing.com/gokarts/functions/"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _post(endpoint: str, data: dict) -> str:
    r = requests.post(API_BASE + endpoint, data=data, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.text


def _strip_and_parse_json(raw: str):
    idx = max(raw.find("{"), raw.find("["))
    return json.loads(raw[idx:]) if idx != -1 else None


def _norm(date_str: str) -> str:
    """'YYYY/MM/DD' or 'YYYY/M/D' -> 'YYYY/M/D' (no leading zeros)."""
    y, m, d = date_str.split("/")
    return f"{y}/{int(m)}/{int(d)}"


def _week_starts(date_keys: list[str]) -> list[str]:
    seen, starts = set(), []
    for key in date_keys:
        y, m, d = (int(x) for x in key.split("/"))
        day = datetime.date(y, m, d)
        monday = day - datetime.timedelta(days=day.weekday())
        wk = f"{monday.year}/{monday.month:02d}/{monday.day:02d}"
        if wk not in seen:
            seen.add(wk)
            starts.append(wk)
    return starts


class ApexTimingProvider(Provider):
    def fetch_availability(self, track: dict, date_keys: list[str]) -> dict:
        if track["mode"] == "sessions":
            return self._fetch_sessions(track["center_id"], track["product_id"], date_keys)
        elif track["mode"] == "calendar":
            return self._fetch_calendar(track["center_id"], track["track_id"], date_keys)
        raise ValueError(f"Unknown apex_timing mode '{track['mode']}' for {track['name']}")

    def _fetch_sessions(self, center_id, product_id, date_keys):
        raw = _post("request_session_booking.php", {
            "type": "session_booking_dates_available",
            "center_id": str(center_id),
            "product_id": str(product_id),
            "dates": json.dumps(date_keys),
            "people_number": "1",
            "kart_id": "",
        })
        result = _strip_and_parse_json(raw)
        if not isinstance(result, dict):
            return {}
        return {
            _norm(k): {"available": bool(v), "label": "Open" if v else "Geen sessies"}
            for k, v in result.items()
        }

    def _fetch_calendar(self, center_id, track_id, date_keys):
        result = {}
        for week_start in _week_starts(date_keys):
            raw = _post("request_calendar.php", {
                "center_id": str(center_id),
                "track_id": str(track_id),
                "date": week_start,
            })
            soup = BeautifulSoup(raw, "html.parser")
            for day_el in soup.find_all("div", class_="days", attrs={"data-date": True}):
                key = _norm(day_el["data-date"])
                li = day_el.find("li", class_="part")
                if li:
                    status = int(li.get("data-status", 0))
                    title = li.get("data-title", "").strip()
                    result[key] = {
                        "available": status == 1,
                        "label": title if title else ("Beschikbaar" if status == 1 else "Gesloten"),
                    }
        return result
