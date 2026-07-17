"""
Builds one row per (center, booking_type) from data/centers_catalog.json.

Each center can contribute rows from two independent sources:
  - `products` (sessions_booking.php catalog) — the common case.
  - `calendar_tracks` (calendar.php resources, see catalog/build_catalog.py's
    fetch_calendar_tracks) — day-based booking systems some centers run
    alongside or instead of the product catalog (e.g. Karting Genk's real
    "own-kart" offering only exists here, not as a product at all).

A calendar-track only becomes a row when it *fills a gap* — i.e. the center
has no product-based row of that same booking type already. This is what
keeps Fagnes (which has both rental and private products AND a redundant
calendar system) from showing duplicate rows, while still surfacing Genk's
private track day, which has no product-based equivalent at all.
"""
import json

from . import config


def load_catalog() -> list[dict]:
    if not config.CATALOG_FILE.exists():
        return []
    return json.loads(config.CATALOG_FILE.read_text(encoding="utf-8"))


def select_rows(catalog: list[dict]) -> list[dict]:
    rows: dict[tuple, dict] = {}

    for center in catalog:
        # Same-booking-type calendar track for this center, if any — kept as a
        # fallback availability source even when a product-based row wins the
        # slot, because a center's product catalog and calendar system aren't
        # guaranteed to be equally reliable for actually checking day-by-day
        # availability. Concretely: Karting Genk's "Track Fee" products (found
        # via catalog/build_catalog.py's merge_duplicate_venues — a separate
        # center_id for the same physical venue) have the better labels/prices,
        # but their availability never comes back non-empty through the normal
        # product API; the calendar system is the one that actually works.
        calendar_by_booking = {t["booking"]: t for t in center.get("calendar_tracks", [])}

        for p in center["products"]:
            key = (center["id"], p["booking"])
            if key not in rows:
                fallback = calendar_by_booking.get(p["booking"])
                rows[key] = {
                    "id": f"{center['id']}:{p['booking']}",
                    "center_id": center["id"],
                    "name": center["name"],
                    "note": "",
                    "website": center["website"],
                    "country": center["country"],
                    "mode": "sessions",
                    "product_id": p["id"],
                    "calendar_fallback_track_id": fallback["track_id"] if fallback else None,
                    "sessions": [],
                    "booking": p["booking"],
                    # One entry per constituent product — a row's "price" isn't
                    # a single number: RACB Spa's Senior class alone is €32
                    # (half day) or €50 (full day), and Genk's Track Fee price
                    # depends entirely on which class you pick (€52 Mini vs.
                    # €72-82 Senior). The frontend turns this into a range when
                    # several classes/durations are in view and narrows to the
                    # exact price once the user filters down to one class.
                    "price_table": [],
                    "booking_url": (
                        f"https://www.apex-timing.com/gokarts/session_booking.php"
                        f"?center={center['id']}&id={p['id']}"
                    ),
                }
            if p["session"] not in rows[key]["sessions"]:
                rows[key]["sessions"].append(p["session"])
            rows[key]["price_table"].append({
                "session": p["session"], "price": p["price"], "dur_h": p["dur_h"],
            })

    for center in catalog:
        for t in center.get("calendar_tracks", []):
            key = (center["id"], t["booking"])
            if key in rows:
                continue  # already covered by a product-based row — don't duplicate
            rows[key] = {
                "id": f"{center['id']}:{t['booking']}",
                "center_id": center["id"],
                "name": center["name"],
                "note": t["name"],
                "website": center["website"],
                "country": center["country"],
                "mode": "calendar",
                "track_id": t["track_id"],
                # No specific age/skill class known for a calendar-discovered
                # track — "general", not t["booking"]: reusing the booking
                # type as the session value is the exact bug this mirrors
                # (see catalog/build_catalog.py's session/booking rename).
                "sessions": ["general"],
                "booking": t["booking"],
                "price_table": [{"session": "general", "price": None, "dur_h": None}],
                "booking_url": (
                    f"https://www.apex-timing.com/gokarts/calendar.php"
                    f"?center={center['id']}&tracks={t['track_id']}&track={t['track_id']}"
                ),
            }

    return sorted(rows.values(), key=lambda r: (r["country"], r["name"], r["booking"]))
