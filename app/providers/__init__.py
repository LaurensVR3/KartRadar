from .apex_timing import ApexTimingProvider
from .manual import ManualProvider
from .ical import ICalProvider

_PROVIDERS = {
    "apex_timing": ApexTimingProvider(),
    "manual": ManualProvider(),
    "ical": ICalProvider(),
}


def get_provider(name: str):
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(f"Unknown provider '{name}' — must be one of {sorted(_PROVIDERS)}")
