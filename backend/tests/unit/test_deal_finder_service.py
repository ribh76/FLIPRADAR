from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from flipradar.services.deal_finder_service import (
    REFRESH_THROTTLE_SECONDS,
    _fair_value_for_listing,
    _is_eligible,
    _last_refresh_at,
    _refresh_universe,
)


def _listing(**overrides):
    values = {
        "marketplace": SimpleNamespace(name="ebay"),
        "external_listing_id": "listing-1",
        "detected_set_number": "75313",
        "lego_set": SimpleNamespace(set_number="75313"),
        "match_confidence": Decimal("95"),
        "exclusion_flags": [],
        "condition": "new",
        "is_sealed": True,
        "currency": "USD",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_eligibility_excludes_duplicate_mismatched_and_low_confidence_listings():
    seen = set()
    assert _is_eligible(_listing(), seen)
    assert not _is_eligible(_listing(), seen)
    assert not _is_eligible(
        _listing(external_listing_id="bad-match", detected_set_number="75192"), seen
    )
    assert not _is_eligible(
        _listing(external_listing_id="low-confidence", match_confidence=Decimal("79")),
        seen,
    )
    assert not _is_eligible(
        _listing(external_listing_id="excluded", exclusion_flags=["parts_only"]), seen
    )


def test_fair_value_uses_the_latest_matching_condition_and_currency():
    listing = _listing()
    older = SimpleNamespace(
        metric_type="fair_market_value",
        condition="new",
        currency="USD",
        value=Decimal("700.00"),
        sample_size=8,
        retrieval_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    latest = SimpleNamespace(
        metric_type="fair_market_value",
        condition="new",
        currency="USD",
        value=Decimal("725.00"),
        sample_size=12,
        retrieval_time=datetime(2026, 2, 1, tzinfo=UTC),
    )
    wrong_currency = SimpleNamespace(
        metric_type="fair_market_value",
        condition="new",
        currency="CAD",
        value=Decimal("900.00"),
        sample_size=99,
        retrieval_time=datetime(2026, 3, 1, tzinfo=UTC),
    )

    assert _fair_value_for_listing(listing, [older, wrong_currency, latest]) == (
        Decimal("725.00"),
        12,
    )


async def test_refresh_throttle_skips_a_second_provider_refresh():
    universe_size = 7
    now = datetime(2026, 8, 5, tzinfo=UTC)
    _last_refresh_at[universe_size] = now

    result = await _refresh_universe(
        db=object(), universe=[], now=now, universe_size=universe_size
    )

    assert result["throttled"] is True
    assert result["retry_after_seconds"] == REFRESH_THROTTLE_SECONDS
    _last_refresh_at.pop(universe_size, None)
