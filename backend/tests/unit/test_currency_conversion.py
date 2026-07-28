from decimal import Decimal

from flipradar.services.currency_conversion import (
    FRANKFURTER_RATE_URL,
    exchange_rate,
)


def test_exchange_rate_calls_frankfurter_with_currency_parameters(monkeypatch):
    exchange_rate.cache_clear()
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"rate": 1.08}

    def fake_get(url, *, timeout):
        captured.update(url=url, timeout=timeout)
        return Response()

    monkeypatch.setattr("flipradar.services.currency_conversion.requests.get", fake_get)

    assert exchange_rate("EUR", "USD") == Decimal("1.08")
    assert captured["url"] == FRANKFURTER_RATE_URL.format(source="EUR", target="USD")
    assert captured["timeout"] > 0
