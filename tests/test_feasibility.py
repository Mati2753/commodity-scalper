from decimal import Decimal

from commodity_scalper.analysis.feasibility import UNKNOWN, analyze_market
from commodity_scalper.capital.models import MarketDetails


def market(currency="USD", lot=100):
    return MarketDetails.model_validate(
        {
            "instrument": {
                "epic": "X",
                "name": "Gold",
                "currency": currency,
                "lotSize": lot,
                "marginFactor": 5,
                "marginFactorUnit": "PERCENTAGE",
            },
            "dealingRules": {"minDealSize": {"value": "0.1"}},
            "snapshot": {"bid": "1999", "offer": "2001"},
        }
    )


def test_feasibility_math_and_honest_three_dollars():
    result = analyze_market("GOLD", market(), (Decimal("3"), Decimal("1000")))
    assert result["approximate_notional_usd"] == "20000.0"
    assert result["estimated_initial_margin_usd"] == "1000.00"
    assert result["current_spread_cost_usd"] == "20.0"
    assert result["balances"][0]["sufficient"] is False
    assert result["balances"][1]["sufficient"] is True


def test_unknown_when_contract_semantics_unproven():
    result = analyze_market("GOLD", market(currency="EUR", lot=None))
    assert result["approximate_notional_usd"] == UNKNOWN
    assert result["balances"][0]["sufficient"] == UNKNOWN
