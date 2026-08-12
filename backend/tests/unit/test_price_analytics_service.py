from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from flipradar.services.price_analytics_service import calculate_price_analytics


def _snapshot(*, days_ago: int, value: str, marketplace_id, sample_size: int = 1):
    return SimpleNamespace(
        retrieval_time=datetime(2026, 8, 12, tzinfo=UTC) - timedelta(days=days_ago),
        value=Decimal(value),
        marketplace_id=marketplace_id,
        sample_size=sample_size,
        condition="new",
    )


def test_calculates_advanced_metrics_from_raw_and_monthly_history():
    first_marketplace = uuid4()
    second_marketplace = uuid4()
    raw = [
        _snapshot(
            days_ago=2, value="100", marketplace_id=first_marketplace, sample_size=8
        ),
        _snapshot(
            days_ago=1, value="120", marketplace_id=first_marketplace, sample_size=10
        ),
        _snapshot(
            days_ago=1, value="110", marketplace_id=second_marketplace, sample_size=5
        ),
    ]
    rollups = [
        SimpleNamespace(
            period="monthly",
            period_start=datetime(2026, 6, 1, tzinfo=UTC).date(),
            average_value=Decimal("150"),
            observation_count=4,
            condition="new",
        ),
        SimpleNamespace(
            period="weekly",
            period_start=datetime(2026, 6, 1, tzinfo=UTC).date(),
            average_value=Decimal("999"),
            observation_count=2,
            condition="new",
        ),
    ]

    result = calculate_price_analytics(
        raw, rollups, now=datetime(2026, 8, 12, tzinfo=UTC)
    )

    assert result["observation_count"] == 7
    assert result["latest_value"] == Decimal("115.00")
    assert result["rolling_averages"]["7d"] == Decimal("107.50")
    assert result["marketplace_spread"]["absolute_spread"] == Decimal("10")
    assert result["marketplace_spread"]["spread_percent_of_low"] == Decimal("9.09")
    assert result["liquidity"] == {
        "latest_marketplace_count": 2,
        "latest_sample_size": 15,
        "observations_30d": 2,
        "proxy_score": 75,
    }
    assert result["drawdown"]["recorded_high"] == Decimal("150.00")
    assert result["drawdown"]["drawdown_percent"] == Decimal("-23.33")
    assert result["volatility"]["return_count"] == 2
    assert result["volatility"]["return_standard_deviation_percent"] == Decimal("24.17")
    assert result["condition_adjusted_comparison"][
        "selected_condition_weight"
    ] == Decimal("1.00")
    assert result["retirement"]["is_retired"] is False
    assert result["inflation_adjusted"]["annual_rate_percent"] == Decimal("4.10")
    assert result["confidence_band"] == {
        "band": 4,
        "max_band": 5,
        "color": "blue",
        "label": "high",
    }
    assert "MAX" in result["chart_controls"]["ranges"]
    assert result["validation_metrics"]["is_valid_for_experiment"] is True


def test_returns_null_for_metrics_without_enough_comparable_history():
    result = calculate_price_analytics([], [], now=datetime(2026, 8, 12, tzinfo=UTC))

    assert result["latest_value"] is None
    assert result["rolling_averages"] == {"7d": None, "30d": None, "90d": None}
    assert result["volatility"]["return_standard_deviation_percent"] is None
    assert result["marketplace_spread"]["absolute_spread"] is None
    assert result["drawdown"]["drawdown_percent"] is None


def test_applies_validated_condition_weights_and_catalog_adjustments():
    marketplace = uuid4()
    snapshots = [
        _snapshot(days_ago=3, value="50", marketplace_id=marketplace),
        _snapshot(days_ago=2, value="60", marketplace_id=marketplace),
        _snapshot(days_ago=1, value="70", marketplace_id=marketplace),
        SimpleNamespace(
            retrieval_time=datetime(2026, 8, 11, tzinfo=UTC),
            value=Decimal("39"),
            marketplace_id=uuid4(),
            sample_size=4,
            condition="used_complete",
        ),
    ]
    lego_set = SimpleNamespace(
        theme="Classic",
        release_year=2000,
        retirement_year=2005,
        msrp=Decimal("40"),
        original_currency="USD",
        data_quality_flag=False,
    )

    result = calculate_price_analytics(
        snapshots,
        [],
        condition="used_complete",
        lego_set=lego_set,
        now=datetime(2026, 8, 12, tzinfo=UTC),
    )

    comparison = result["condition_adjusted_comparison"]
    assert comparison["conditions"]["used_complete"]["weight"] == Decimal("0.78")
    assert comparison["conditions"]["used_complete"]["new_equivalent_value"] == Decimal(
        "50.00"
    )
    assert result["theme_benchmark"]["benchmark_index"] == Decimal("135.00")
    assert result["retirement"]["years_retired"] == 21
    assert result["retirement"]["rarity_multiplier"] == Decimal("1.30")
    assert result["msrp_comparison"]["difference_amount"] == Decimal("-1.00")
    assert result["inflation_adjusted"]["inflation_adjusted_msrp"] == Decimal("113.70")
