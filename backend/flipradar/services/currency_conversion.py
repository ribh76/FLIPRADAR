"""Currency conversion backed by Frankfurter, retaining source price evidence."""

from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

import requests

FRANKFURTER_RATE_URL = "https://api.frankfurter.dev/v2/rate/{source}/{target}"
DEFAULT_TIMEOUT_SECONDS = 10


class CurrencyConversionError(RuntimeError):
    """Raised when a requested conversion rate is unavailable."""


@lru_cache(maxsize=128)
def exchange_rate(source_currency: str, target_currency: str) -> Decimal:
    """Fetch the latest source-to-target rate from Frankfurter."""
    source = source_currency.upper()
    target = target_currency.upper()
    if source == target:
        return Decimal("1")
    try:
        response = requests.get(
            FRANKFURTER_RATE_URL.format(source=source, target=target),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        rate = response.json()["rate"]
        return Decimal(str(rate))
    except (KeyError, requests.RequestException, ValueError) as exc:
        raise CurrencyConversionError(
            f"Unable to fetch {source}->{target} exchange rate"
        ) from exc


def convert(value: Decimal, source_currency: str, target_currency: str) -> Decimal:
    return (value * exchange_rate(source_currency, target_currency)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
