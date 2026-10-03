"""Raw quote and derived microstructure fields."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class Tick(BaseModel):
    model_config = ConfigDict(frozen=True)
    exchange_timestamp: datetime
    received_timestamp: datetime
    epic: str
    bid: Decimal
    ask: Decimal
    bid_quantity: Decimal | None = None
    ask_quantity: Decimal | None = None
    mid: Decimal
    spread_absolute: Decimal
    spread_bps: Decimal

    @field_validator("exchange_timestamp", "received_timestamp")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_quote(self) -> "Tick":
        if not self.epic:
            raise ValueError("epic is required")
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid and ask must be positive")
        if self.ask < self.bid:
            raise ValueError("ask must not be below bid")
        return self

    @classmethod
    def from_quote(
        cls,
        *,
        epic: str,
        bid: Decimal | str | float,
        ask: Decimal | str | float,
        exchange_timestamp: datetime,
        received_timestamp: datetime | None = None,
        bid_quantity: Decimal | None = None,
        ask_quantity: Decimal | None = None,
    ) -> "Tick":
        bid_d, ask_d = Decimal(str(bid)), Decimal(str(ask))
        mid = (bid_d + ask_d) / 2
        spread = ask_d - bid_d
        return cls(
            exchange_timestamp=exchange_timestamp,
            received_timestamp=received_timestamp or datetime.now(UTC),
            epic=epic,
            bid=bid_d,
            ask=ask_d,
            bid_quantity=bid_quantity,
            ask_quantity=ask_quantity,
            mid=mid,
            spread_absolute=spread,
            spread_bps=spread / mid * Decimal(10000),
        )
