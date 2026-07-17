from .base import Provider


class ManualProvider(Provider):
    """
    Fallback for a track with no live-availability integration at all — just
    a booking_url link-out card, rendered as "unknown" for every date. Use
    this to add a track today and wire up a real provider for it later.
    """

    def fetch_availability(self, track: dict, date_keys: list[str]) -> dict:
        return {}
