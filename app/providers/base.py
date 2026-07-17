from abc import ABC, abstractmethod


class Provider(ABC):
    """
    A track's availability source. One instance per provider *type*, reused
    across every track configured with that provider in tracks.yaml — track-
    specific config (center_id, product_id, URL, ...) is passed in per call,
    not held on the instance.
    """

    @abstractmethod
    def fetch_availability(self, track: dict, date_keys: list[str]) -> dict:
        """
        track: one entry from tracks.yaml (already includes 'provider').
        date_keys: dates to check, formatted "YYYY/M/D" (no leading zeros).

        Returns {date_key: {"available": bool, "label": str}}. Dates with no
        data at all should simply be omitted from the result (renders as
        "unknown", not "closed").
        """
        raise NotImplementedError
