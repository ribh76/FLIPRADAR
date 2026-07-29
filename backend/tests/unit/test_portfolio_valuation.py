from decimal import Decimal

from flipradar.domain.engines.portfolio_valuation import (
    calculate_holding_valuation,
    calculate_portfolio_totals,
)


def test_holding_valuation_calculates_cost_market_value_and_return():
    valuation = calculate_holding_valuation(
        quantity=2,
        purchase_price=Decimal("75.00"),
        unit_market_value=Decimal("110.00"),
    )

    assert valuation.cost_basis == Decimal("150.00")
    assert valuation.market_value == Decimal("220.00")
    assert valuation.unrealized_gain_loss == Decimal("70.00")
    assert valuation.unrealized_gain_loss_percent == Decimal("46.67")


def test_unvalued_holding_keeps_cost_basis_but_excludes_return_metrics():
    valuation = calculate_holding_valuation(
        quantity=1,
        purchase_price=Decimal("50.00"),
        unit_market_value=None,
    )

    assert valuation.cost_basis == Decimal("50.00")
    assert valuation.market_value is None
    assert valuation.unrealized_gain_loss is None
    assert valuation.unrealized_gain_loss_percent is None


def test_portfolio_totals_only_include_valued_holdings_in_gain_loss():
    valued = calculate_holding_valuation(
        quantity=1,
        purchase_price=Decimal("100.00"),
        unit_market_value=Decimal("125.00"),
    )
    unvalued = calculate_holding_valuation(
        quantity=1,
        purchase_price=Decimal("50.00"),
        unit_market_value=None,
    )

    totals = calculate_portfolio_totals([valued, unvalued])

    assert totals == {
        "total_cost_basis": Decimal("150.00"),
        "total_market_value": Decimal("125.00"),
        "total_gain_loss": Decimal("25.00"),
        "total_gain_loss_percent": Decimal("25.00"),
    }
