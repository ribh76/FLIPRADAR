"""Exact, auditable valuation calculations for portfolio holdings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class HoldingValuation:
    cost_basis: Decimal
    market_value: Decimal | None
    unrealized_gain_loss: Decimal | None
    unrealized_gain_loss_percent: Decimal | None


def calculate_holding_valuation(
    *,
    quantity: int,
    purchase_price: Decimal,
    unit_market_value: Decimal | None,
) -> HoldingValuation:
    """Calculate value and return for one independently recorded purchase."""
    cost_basis = _money(Decimal(quantity) * purchase_price)
    if unit_market_value is None:
        return HoldingValuation(cost_basis, None, None, None)

    market_value = _money(Decimal(quantity) * unit_market_value)
    gain_loss = _money(market_value - cost_basis)
    gain_loss_percent = (
        _money(gain_loss / cost_basis * Decimal("100")) if cost_basis > 0 else None
    )
    return HoldingValuation(cost_basis, market_value, gain_loss, gain_loss_percent)


def calculate_portfolio_totals(
    holdings: Sequence[HoldingValuation],
) -> dict[str, Decimal | None]:
    """Aggregate values and returns without converting currency to floats."""
    total_cost_basis = _money(
        sum(
            (holding.cost_basis or Decimal("0.00") for holding in holdings),
            Decimal("0.00"),
        )
    )
    valued_holdings = [
        holding for holding in holdings if holding.market_value is not None
    ]
    total_market_value = _money(
        sum(
            (holding.market_value or Decimal("0.00") for holding in valued_holdings),
            Decimal("0.00"),
        )
    )
    valued_cost_basis = _money(
        sum(
            (holding.cost_basis or Decimal("0.00") for holding in valued_holdings),
            Decimal("0.00"),
        )
    )
    total_gain_loss = _money(total_market_value - valued_cost_basis)
    total_gain_loss_percent = (
        _money(total_gain_loss / valued_cost_basis * Decimal("100"))
        if valued_cost_basis > 0
        else None
    )
    return {
        "total_cost_basis": total_cost_basis,
        "total_market_value": total_market_value,
        "total_gain_loss": total_gain_loss,
        "total_gain_loss_percent": total_gain_loss_percent,
    }
