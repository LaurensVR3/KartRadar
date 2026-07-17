import asyncio
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

from . import browse, config
from .cache import CACHE
from .providers import get_provider

log = logging.getLogger("scheduler")

_executor = ThreadPoolExecutor(max_workers=40)


def _date_keys(days_ahead: int) -> list[str]:
    today = datetime.date.today()
    return [
        f"{d.year}/{d.month}/{d.day}"
        for d in (today + datetime.timedelta(days=i) for i in range(days_ahead))
    ]


async def refresh_all():
    """
    Refresh availability for every auto-discovered row (products + gap-filling
    calendar tracks, see app/browse.py) plus any hand-configured tracks.yaml
    entries. tracks.yaml is empty of Apex Timing tracks now that discovery
    covers them automatically — the manual/ical path stays wired up for
    whenever a genuinely non-Apex track gets added.
    """
    date_keys = _date_keys(config.DAYS_AHEAD)
    loop = asyncio.get_event_loop()
    apex = get_provider("apex_timing")

    catalog = browse.load_catalog()
    rows = browse.select_rows(catalog)

    async def refresh_catalog_row(row):
        pseudo_track = {"name": row["name"], "mode": row["mode"], "center_id": row["center_id"]}
        if row["mode"] == "sessions":
            pseudo_track["product_id"] = row["product_id"]
        else:
            pseudo_track["track_id"] = row["track_id"]
        try:
            avail = await loop.run_in_executor(_executor, apex.fetch_availability, pseudo_track, date_keys)
        except Exception:
            avail = {}

        # The product API came back with nothing open across the whole window
        # — before trusting that, try the center's calendar system if one
        # exists for this booking type. A completely dead-looking product API
        # is more often a broken/unsupported availability check for that
        # specific product (see Karting Genk's Track Fee tickets) than a
        # venue that's really closed for 28 straight days.
        fallback_track_id = row.get("calendar_fallback_track_id")
        if fallback_track_id and not any(v.get("available") for v in avail.values()):
            try:
                fallback_track = {"name": row["name"], "mode": "calendar",
                                   "center_id": row["center_id"], "track_id": fallback_track_id}
                fallback_avail = await loop.run_in_executor(
                    _executor, apex.fetch_availability, fallback_track, date_keys)
                if any(v.get("available") for v in fallback_avail.values()):
                    avail = fallback_avail
            except Exception:
                pass

        row_out = dict(row)
        row_out["availability"] = avail
        return f"catalog:{row['id']}", row_out

    catalog_results = await asyncio.gather(*(refresh_catalog_row(r) for r in rows))

    extra_tracks = config.load_tracks()

    async def refresh_extra_track(track):
        provider = get_provider(track["provider"])
        try:
            avail = await loop.run_in_executor(_executor, provider.fetch_availability, track, date_keys)
        except Exception:
            log.exception("Refresh failed for track '%s'", track["name"])
            avail = {}
        row = {
            "id": f"manual:{track['name']}",
            "center_id": None,
            "name": track["name"],
            "note": track.get("note", ""),
            "website": track["booking_url"],
            "country": track.get("country", "??"),
            "mode": track["provider"],
            # No specific age/skill class known — "general", not the booking
            # type (reusing booking as the session value is the exact bug
            # fixed elsewhere; see catalog/build_catalog.py and app/browse.py).
            "sessions": [track.get("session", "general")],
            "booking": track.get("booking", "private"),
            "price_table": [{"session": track.get("session", "general"), "price": None, "dur_h": None}],
            "booking_url": track["booking_url"],
            "availability": avail,
        }
        return f"manual:{track['name']}", row

    extra_results = await asyncio.gather(*(refresh_extra_track(t) for t in extra_tracks))

    CACHE.set_rows(dict(catalog_results) | dict(extra_results))
    log.info("Refreshed %d catalog rows + %d manually configured tracks",
              len(catalog_results), len(extra_results))


async def rebuild_catalog():
    from catalog import build_catalog
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, build_catalog.build)
    log.info("Rebuilt centers_catalog.json")


async def daily_refresh():
    """Full refresh: rediscover centers (+ their calendar tracks), then re-check
    availability for everything."""
    await rebuild_catalog()
    await refresh_all()
    log.info("Daily refresh complete")


async def refresh_loop():
    # Run once immediately on startup so the page isn't empty until the next
    # scheduled daily refresh.
    if not config.CATALOG_FILE.exists():
        await rebuild_catalog()

    await refresh_all()

    last_run_date = datetime.date.today()  # skip a same-day rerun right after the one above

    while True:
        await asyncio.sleep(60)
        now = datetime.datetime.now()

        if now.hour == config.DAILY_REFRESH_HOUR and now.date() != last_run_date:
            await daily_refresh()
            last_run_date = now.date()
