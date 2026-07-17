"""
Generic ICS-feed provider, for booking systems that publish a calendar feed
instead of (or in addition to) an availability API.

Track config:
  ics_url: URL of the .ics feed
  event_meaning: "busy" (default) — a day with an event on it is NOT bookable
                 "available" — a day with an event on it IS bookable
Which one applies depends entirely on what the specific feed represents; check
by comparing a couple of dates against the track's own site before trusting it.
"""
import requests
from icalendar import Calendar

from .base import Provider


class ICalProvider(Provider):
    def fetch_availability(self, track: dict, date_keys: list[str]) -> dict:
        r = requests.get(track["ics_url"], timeout=15)
        r.raise_for_status()
        cal = Calendar.from_ical(r.content)

        event_days = set()
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            dtstart = component.get("dtstart")
            if dtstart is None:
                continue
            d = dtstart.dt
            date_part = d.date() if hasattr(d, "date") else d
            event_days.add(f"{date_part.year}/{date_part.month}/{date_part.day}")

        meaning = track.get("event_meaning", "busy")
        result = {}
        for key in date_keys:
            has_event = key in event_days
            if meaning == "available":
                available = has_event
            else:
                available = not has_event
            result[key] = {
                "available": available,
                "label": "Open" if available else "Booked" if has_event else "Closed",
            }
        return result
