"""Vectorized, auditable valuation calculations for portfolio holdings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
    cost_basis = _money(np.multiply(float(quantity), float(purchase_price)))
    if unit_market_value is None:
        return HoldingValuation(cost_basis, None, None, None)

    market_value = _money(np.multiply(float(quantity), float(unit_market_value)))
    gain_loss = _money(float(market_value) - float(cost_basis))
    gain_loss_percent = (
        _money(np.divide(float(gain_loss), float(cost_basis)) * 100)
        if cost_basis > 0
        else None
    )
    return HoldingValuation(cost_basis, market_value, gain_loss, gain_loss_percent)


def calculate_portfolio_totals(
    holdings: Sequence[HoldingValuation],
) -> dict[str, Decimal | None]:
    """Aggregate current values and returns using NumPy arrays in one pass."""
    cost_basis = np.asarray([float(holding.cost_basis) for holding in holdings])
    market_values = np.asarray(
        [
            float(holding.market_value)
            for holding in holdings
            if holding.market_value is not None
        ]
    )
    valued_cost_basis = np.asarray(
        [
            float(holding.cost_basis)
            for holding in holdings
            if holding.market_value is not None
        ]
    )
    total_cost_basis = (
        _money(np.sum(cost_basis)) if cost_basis.size else Decimal("0.00")
    )
    total_market_value = (
        _money(np.sum(market_values)) if market_values.size else Decimal("0.00")
    )
    total_gain_loss = _money(total_market_value - _money(np.sum(valued_cost_basis)))
    total_gain_loss_percent = (
        _money(np.divide(float(total_gain_loss), np.sum(valued_cost_basis)) * 100)
        if valued_cost_basis.size and np.sum(valued_cost_basis) > 0
        else None
    )
    return {
        "total_cost_basis": total_cost_basis,
        "total_market_value": total_market_value,
        "total_gain_loss": total_gain_loss,
        "total_gain_loss_percent": total_gain_loss_percent,
    }
