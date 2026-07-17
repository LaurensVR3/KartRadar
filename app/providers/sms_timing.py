"""
SMS-Timing / BMI Leisure provider — a genuine Apex Timing competitor, served
as a white-labeled skin under multiple domains (booking.sms-timing.com,
booking.bmileisure.com, ...) that all hit the same backend and clientKey. No
public directory of clients exists (checked their marketing sites, sitemaps,
and a handful of likely API paths) — each venue is added by hand once we know
its client_key, product_id and page_id (read off GET
https://booking-api7.sms-timing.com/api/settings/{client_key}).

The availability check itself is a cheap plain POST once you hold a valid
access token — but getting that token means replicating a client-side AES
handshake, deliberately not reverse-engineered here (fragile: breaks silently
whenever they redeploy their JS bundle, for uncertain payoff). Instead we get
it the same way the real page does — drive one page load with a headless
browser and read the token off whichever request the page itself makes — and
cache it, since it was confirmed to stay valid across many separate calls,
not just the one page load that produced it.

Track config:
  client_key: e.g. "kartingdelandsard"
  product_id, page_id: which bookable product/page to check
  booking_url: the venue's booking front-end, used both for linking out and
    as the page a token refresh loads
"""
import datetime
import json
import logging
import uuid

import requests

from .. import config
from .base import Provider

log = logging.getLogger(__name__)

API_BASE = "https://booking-api7.sms-timing.com/api"
TOKEN_CACHE_FILE = config.DATA_DIR / "sms_timing_tokens.json"
TOKEN_MAX_AGE_HOURS = 20  # refresh well before a ~24h cycle turns over


def _load_token_cache() -> dict:
    if not TOKEN_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_token_cache(cache: dict):
    TOKEN_CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _fetch_fresh_token(client_key: str, booking_url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("playwright not installed — cannot refresh SMS-Timing token")
        return None

    token = None

    def handle_request(request):
        nonlocal token
        if token is None and "booking-api7.sms-timing.com" in request.url:
            t = request.headers.get("x-fast-accesstoken")
            if t:
                token = t

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.on("request", handle_request)
            page.goto(booking_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)
            browser.close()
    except Exception:
        log.exception("Playwright token refresh failed for %s", client_key)
        return None

    return token


def _get_token(client_key: str, booking_url: str, force_refresh: bool = False) -> str | None:
    cache = _load_token_cache()
    entry = cache.get(client_key)

    if not force_refresh and entry:
        fetched_at = datetime.datetime.fromisoformat(entry["fetched_at"])
        age_hours = (datetime.datetime.now() - fetched_at).total_seconds() / 3600
        if age_hours < TOKEN_MAX_AGE_HOURS:
            return entry["token"]

    token = _fetch_fresh_token(client_key, booking_url)
    if token:
        cache[client_key] = {"token": token, "fetched_at": datetime.datetime.now().isoformat()}
        _save_token_cache(cache)
        return token

    # Refresh failed — fall back to whatever's cached, even if stale, rather
    # than going dark for the day.
    return entry["token"] if entry else None


class SmsTimingProvider(Provider):
    def fetch_availability(self, track: dict, date_keys: list[str]) -> dict:
        if not date_keys:
            return {}

        client_key = track["client_key"]
        dates = sorted(datetime.date(*map(int, k.split("/"))) for k in date_keys)
        date_from, date_until = dates[0], dates[-1]

        token = _get_token(client_key, track["booking_url"])
        if not token:
            return {}

        data = self._request_calendarrange(client_key, track, date_from, date_until, token)
        if data is None:
            # Cached token stopped working (or first-time refresh failed) — try once more with a forced refresh.
            token = _get_token(client_key, track["booking_url"], force_refresh=True)
            if not token:
                return {}
            data = self._request_calendarrange(client_key, track, date_from, date_until, token)
            if data is None:
                return {}

        open_days = {d[:10] for d in data.get("days", [])}  # "2026-07-17T00:00:00" -> "2026-07-17"
        result = {}
        for key in date_keys:
            d = datetime.date(*map(int, key.split("/")))
            available = d.isoformat() in open_days
            result[key] = {"available": available, "label": "Open" if available else "Vol / gesloten"}
        return result

    def _request_calendarrange(self, client_key, track, date_from, date_until, token):
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://booking.sms-timing.com/",
            "x-fast-accesstoken": token,
            "x-session-id": str(uuid.uuid4()),
        }
        try:
            r = requests.post(
                f"{API_BASE}/dayplanner/calendarrange/{client_key}",
                params={"dateFrom": date_from.isoformat(), "dateUntil": date_until.isoformat()},
                headers=headers,
                json={"productId": track["product_id"], "pageId": track["page_id"], "quantity": 1},
                timeout=15,
            )
            if r.status_code == 401:
                return None
            r.raise_for_status()
            return r.json()
        except Exception:
            log.exception("SMS-Timing availability check failed for %s", client_key)
            return None
