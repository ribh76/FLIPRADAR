from decimal import Decimal

import pytest
from pydantic import ValidationError

from flipradar.api.schemas.recommendation_schema import ManualValuationOverride


def test_manual_valuation_override_accepts_a_documented_range():
    override = ManualValuationOverride(
        expected_value=Decimal("200.00"),
        low_value=Decimal("180.00"),
        high_value=Decimal("220.00"),
        reason="Recent verified collector sale.",
    )

    assert override.expected_value == Decimal("200.00")


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_value": "200.00", "reason": "ok"},
        {
            "expected_value": "200.00",
            "low_value": "210.00",
            "reason": "Recent verified collector sale.",
        },
    ],
)
def test_manual_valuation_override_rejects_missing_reason_or_invalid_range(payload):
    with pytest.raises(ValidationError):
        ManualValuationOverride(**payload)
