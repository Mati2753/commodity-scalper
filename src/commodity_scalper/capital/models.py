"""Tolerant models for Capital.com response payloads."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class UnitValue(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    value: Decimal | None = None
    unit: str | None = None


class Instrument(BaseModel):
    model_config = ConfigDict(extra="allow")
    epic: str
    name: str
    symbol: str | None = None
    type: str | None = None
    currency: str | None = None
    lotSize: Decimal | None = None
    marginFactor: Decimal | None = None
    marginFactorUnit: str | None = None
    streamingPricesAvailable: bool | None = None
    openingHours: dict[str, Any] | None = None


class DealingRules(BaseModel):
    model_config = ConfigDict(extra="allow")
    minDealSize: UnitValue | None = None
    maxDealSize: UnitValue | None = None
    minSizeIncrement: UnitValue | None = None
    minStepDistance: UnitValue | None = None
    minStopOrProfitDistance: UnitValue | None = None
    maxStopOrProfitDistance: UnitValue | None = None


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="allow")
    marketStatus: str | None = None
    bid: Decimal | None = None
    offer: Decimal | None = None


class MarketDetails(BaseModel):
    model_config = ConfigDict(extra="allow")
    instrument: Instrument
    dealingRules: DealingRules
    snapshot: Snapshot


class MarketCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")
    epic: str
    instrumentName: str = ""
    instrumentType: str | None = None
    marketStatus: str | None = None
    bid: Decimal | None = None
    offer: Decimal | None = None
