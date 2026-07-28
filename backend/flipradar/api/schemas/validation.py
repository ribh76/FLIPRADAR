from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator

from flipradar.domain.models.enums import (
    ListingCondition,
    MarketplaceName,
    PortfolioCondition,
    PriceMetricType,
    SnapshotCondition,
)

MONEY_QUANT = Decimal("0.01")


def normalize_set_number(value: Any) -> str:
    return str(value).strip().upper()


def normalize_lower_text(value: Any) -> str:
    return str(value).strip().lower()


def quantize_money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(MONEY_QUANT)


SetNumber = Annotated[str, BeforeValidator(normalize_set_number)]
LowerText = Annotated[str, BeforeValidator(normalize_lower_text)]
MarketplaceValue = Annotated[MarketplaceName, BeforeValidator(normalize_lower_text)]
ListingConditionValue = Annotated[
    ListingCondition, BeforeValidator(normalize_lower_text)
]
PortfolioConditionValue = Annotated[
    PortfolioCondition, BeforeValidator(normalize_lower_text)
]
SnapshotConditionValue = Annotated[
    SnapshotCondition, BeforeValidator(normalize_lower_text)
]
PriceMetricTypeValue = Annotated[PriceMetricType, BeforeValidator(normalize_lower_text)]
Money = Annotated[Decimal, AfterValidator(quantize_money)]
OptionalMoney = Annotated[Decimal | None, AfterValidator(quantize_money)]
