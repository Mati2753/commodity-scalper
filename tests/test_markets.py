import pytest

from commodity_scalper.capital.markets import choose_candidate
from commodity_scalper.capital.models import MarketCandidate, MarketDetails


def candidate(epic, name, kind="COMMODITIES"):
    return MarketCandidate(
        epic=epic, instrumentName=name, instrumentType=kind, marketStatus="TRADEABLE"
    )


def test_market_selection_rejects_unrelated_and_selects_specific():
    result = choose_candidate(
        "WTI", [candidate("ETF", "Crude Oil ETF", "SHARES"), candidate("DYNAMIC", "WTI Crude Oil")]
    )
    assert result.epic == "DYNAMIC"


def test_market_selection_requires_unambiguous_result():
    with pytest.raises(ValueError, match="Ambiguous"):
        choose_candidate("GOLD", [candidate("A", "Gold Spot"), candidate("B", "Gold Future")])


def test_full_instrument_parsing():
    details = MarketDetails.model_validate(
        {
            "instrument": {
                "epic": "DYNAMIC",
                "name": "Gold",
                "symbol": "XAUUSD",
                "type": "COMMODITIES",
                "currency": "USD",
                "lotSize": 100,
                "marginFactor": 5,
                "marginFactorUnit": "PERCENTAGE",
                "streamingPricesAvailable": True,
                "openingHours": {},
            },
            "dealingRules": {
                "minDealSize": {"value": 0.1, "unit": "POINTS"},
                "maxDealSize": {"value": 10, "unit": "POINTS"},
                "minSizeIncrement": {"value": 0.1},
                "minStepDistance": {"value": 1},
                "minStopOrProfitDistance": {"value": 1},
                "maxStopOrProfitDistance": {"value": 100},
            },
            "snapshot": {"marketStatus": "TRADEABLE", "bid": 2000, "offer": 2001},
        }
    )
    assert details.instrument.epic == "DYNAMIC"
    assert details.dealingRules.minDealSize.value is not None
