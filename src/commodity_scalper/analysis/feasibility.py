"""Conservative minimum-position feasibility calculations."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from commodity_scalper.capital.models import MarketDetails

BALANCES = tuple(Decimal(str(x)) for x in (3, 5, 10, 25, 50, 100, 250, 500))
UNKNOWN = "UNKNOWN — additional contract information required"


def analyze_market(
    label: str, market: MarketDetails, balances: tuple[Decimal, ...] = BALANCES
) -> dict[str, Any]:
    instrument, rules, snapshot = market.instrument, market.dealingRules, market.snapshot
    size = rules.minDealSize.value if rules.minDealSize else None
    mid = (
        (snapshot.bid + snapshot.offer) / 2
        if snapshot.bid is not None and snapshot.offer is not None
        else None
    )
    can_value = (
        size is not None
        and mid is not None
        and instrument.lotSize is not None
        and (instrument.currency or "").upper() == "USD"
    )
    notional = size * instrument.lotSize * mid if can_value else None
    spread_cost = (snapshot.offer - snapshot.bid) * size * instrument.lotSize if can_value else None
    margin = None
    if notional is not None and instrument.marginFactor is not None:
        unit = (instrument.marginFactorUnit or "").upper()
        if unit == "PERCENTAGE":
            margin = notional * instrument.marginFactor / 100
        elif unit in {"DECIMAL", "MULTIPLIER"}:
            margin = notional * instrument.marginFactor
    rows = []
    for balance in balances:
        rows.append(
            {
                "balance_usd": str(balance),
                "sufficient": balance >= margin if margin is not None else UNKNOWN,
                "margin_utilization_percent": str(margin / balance * 100)
                if margin is not None
                else UNKNOWN,
            }
        )
    notes = []
    if not can_value:
        notes.append(UNKNOWN + ": USD conversion and/or contract lot semantics are unavailable.")
    if margin is None:
        notes.append(UNKNOWN + ": margin factor semantics or notional exposure are unavailable.")
    return {
        "commodity": label,
        "epic": instrument.epic,
        "currency": instrument.currency,
        "minimum_trade_size": str(size) if size is not None else UNKNOWN,
        "lot_size": str(instrument.lotSize) if instrument.lotSize is not None else UNKNOWN,
        "mid_price": str(mid) if mid is not None else UNKNOWN,
        "approximate_notional_usd": str(notional) if notional is not None else UNKNOWN,
        "estimated_initial_margin_usd": str(margin) if margin is not None else UNKNOWN,
        "current_spread_cost_usd": str(spread_cost) if spread_cost is not None else UNKNOWN,
        "balances": rows,
        "notes": notes,
    }


def create_report(markets: dict[str, MarketDetails], path: Path) -> dict[str, Any]:
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "warning": (
            "Research estimate only; verify contract semantics with Capital.com "
            "before relying on it."
        ),
        "markets": [analyze_market(label, market) for label, market in markets.items()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return report
