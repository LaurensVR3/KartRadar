from .apex_timing import ApexTimingProvider
from .manual import ManualProvider
from .ical import ICalProvider
from .woocommerce_variations import WooCommerceVariationsProvider
from .sms_timing import SmsTimingProvider

_PROVIDERS = {
    "apex_timing": ApexTimingProvider(),
    "manual": ManualProvider(),
    "ical": ICalProvider(),
    "woocommerce_variations": WooCommerceVariationsProvider(),
    "sms_timing": SmsTimingProvider(),
}


def get_provider(name: str):
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(f"Unknown provider '{name}' — must be one of {sorted(_PROVIDERS)}")
