"""
Generic provider for WooCommerce product pages that use a "pick a date"
variation attribute instead of a real booking calendar — common among small
European venue sites (WordPress + WooCommerce is extremely widespread).
Confirmed against Circuit de Landsard's (outdoorkarting.nl) own-kart training
day product, which lists every open date as a plain product variation.

Track config:
  product_url: the WooCommerce product page, e.g.
    "https://outdoorkarting.nl/product/trainingsdagkaart-karting-eindhoven/"
  date_attribute: the variation attribute holding the date (default
    "attribute_datum" — Dutch for "date"; WooCommerce derives this from
    whatever the site calls its "Datum"/"Date" attribute, so a different site
    may need a different value here)
  locale: only "nl" (Dutch month names) is implemented so far

No auth, no session handshake — a single GET returns everything: WooCommerce
embeds a `data-product_variations` HTML attribute containing a JSON array of
every variation, each with `is_in_stock`/`is_purchasable` flags.
"""
import datetime
import html
import json
import re

import requests

from .base import Provider

_NL_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}

_DATE_RE = re.compile(r"(\d{1,2})\s+([a-zA-Zé]+)")


def _parse_dutch_date(text: str, today: datetime.date) -> datetime.date | None:
    """'Vrijdag 17 Juli' -> a real date. No year in the string, so infer it:
    this year, unless that would already be well in the past, then next year."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    day = int(m.group(1))
    month = _NL_MONTHS.get(m.group(2).lower())
    if month is None:
        return None
    year = today.year
    try:
        d = datetime.date(year, month, day)
    except ValueError:
        return None
    if (today - d).days > 60:
        d = datetime.date(year + 1, month, day)
    return d


class WooCommerceVariationsProvider(Provider):
    def fetch_availability(self, track: dict, date_keys: list[str]) -> dict:
        r = requests.get(track["product_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()

        m = re.search(r'data-product_variations="([^"]*)"', r.text)
        if not m:
            return {}
        variations = json.loads(html.unescape(m.group(1)))

        date_attr = track.get("date_attribute", "attribute_datum")
        today = datetime.date.today()
        result = {}
        for v in variations:
            raw_date = v.get("attributes", {}).get(date_attr)
            if not raw_date:
                continue
            d = _parse_dutch_date(raw_date, today)
            if d is None:
                continue
            available = bool(v.get("is_in_stock")) and bool(v.get("is_purchasable"))
            key = f"{d.year}/{d.month}/{d.day}"
            result[key] = {
                "available": available,
                "label": "Open" if available else "Vol / gesloten",
            }
        return result
