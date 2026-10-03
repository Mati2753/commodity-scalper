from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from commodity_scalper.data.tick import Tick


def test_spread_calculations():
    tick = Tick.from_quote(
        epic="GOLD.TEST", bid="1999", ask="2001", exchange_timestamp=datetime.now(UTC)
    )
    assert tick.mid == Decimal("2000")
    assert tick.spread_absolute == Decimal("2")
    assert tick.spread_bps == Decimal("10")


@pytest.mark.parametrize("bid,ask", [(0, 1), (1, 0), (2, 1)])
def test_invalid_quote(bid, ask):
    with pytest.raises(ValidationError):
        Tick.from_quote(epic="X", bid=bid, ask=ask, exchange_timestamp=datetime.now(UTC))


def test_timestamp_must_be_aware():
    with pytest.raises(ValidationError):
        Tick.from_quote(epic="X", bid=1, ask=2, exchange_timestamp=datetime.now())
