from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from flipradar.services.deal_finder_service import (
    REFRESH_THROTTLE_SECONDS,
    DealFilters,
    _fair_value_for_listing,
    _filter_and_sort_deals,
    _is_eligible,
    _last_refresh_at,
    _refresh_universe,
)


def _deal(**overrides):
    deal = {
        "total_cost": Decimal("200.00"),
        "shipping_price": Decimal("10.00"),
        "theme": "Star Wars",
        "subtheme": "Ultimate Collector Series",
        "release_year": 2021,
        "age_years": 5,
        "condition": "new",
        "is_sealed": True,
        "retirement_status": "retired",
        "marketplace": {"name": "ebay"},
        "discount": Decimal("25.0"),
        "confidence": 90,
        "score": 80,
    }
    deal.update(overrides)
    return deal


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


def test_deal_filters_apply_catalog_listing_and_threshold_preferences():
    matching = _deal()
    too_expensive = _deal(total_cost=Decimal("450.00"))
    wrong_marketplace = _deal(marketplace={"name": "bricklink"})

    filtered = _filter_and_sort_deals(
        [too_expensive, wrong_marketplace, matching],
        DealFilters(
            max_budget=Decimal("250.00"),
            theme="star wars",
            min_release_year=2020,
            min_age_years=4,
            condition="sealed",
            retirement_status="retired",
            marketplace="ebay",
            min_discount=Decimal("20"),
            min_confidence=85,
            max_shipping=Decimal("15"),
        ),
    )

    assert filtered == [matching]


def test_deal_sorting_supports_discount_price_and_confidence():
    low_price = _deal(total_cost=Decimal("100"), discount=Decimal("10"), confidence=70)
    high_discount = _deal(
        total_cost=Decimal("300"), discount=Decimal("30"), confidence=80
    )
    high_confidence = _deal(
        total_cost=Decimal("250"), discount=Decimal("20"), confidence=95
    )

    assert (
        _filter_and_sort_deals(
            [low_price, high_discount, high_confidence],
            DealFilters(order="discount_desc"),
        )[0]
        is high_discount
    )
    assert (
        _filter_and_sort_deals(
            [high_discount, high_confidence, low_price],
            DealFilters(order="total_price_asc"),
        )[0]
        is low_price
    )
    assert (
        _filter_and_sort_deals(
            [low_price, high_discount, high_confidence],
            DealFilters(order="confidence_desc"),
        )[0]
        is high_confidence
    )


def test_deal_filter_validation_rejects_invalid_ranges_and_values():
    try:
        DealFilters(min_budget=Decimal("100"), max_budget=Decimal("50")).validate()
    except ValueError as exc:
        assert str(exc) == "minimum budget cannot exceed maximum budget"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected invalid budget range")
