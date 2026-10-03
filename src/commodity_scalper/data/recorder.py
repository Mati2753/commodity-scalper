"""Tick validation, statistics, periodic and shutdown flushing."""

import asyncio
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from commodity_scalper.data.storage import ParquetTickStorage
from commodity_scalper.data.tick import Tick

log = logging.getLogger(__name__)


@dataclass
class RecorderStats:
    received: int = 0
    stored: int = 0
    rejected: int = 0
    reconnections: int = 0
    max_gap_seconds: float = 0.0
    spreads: list[float] = field(default_factory=list)
    last_by_epic: dict[str, datetime] = field(default_factory=dict)

    def summary(self) -> dict[str, float | int | None]:
        return {
            "ticks_received": self.received,
            "ticks_stored": self.stored,
            "ticks_rejected": self.rejected,
            "reconnections": self.reconnections,
            "maximum_gap_seconds": self.max_gap_seconds,
            "average_spread": statistics.fmean(self.spreads) if self.spreads else None,
            "median_spread": statistics.median(self.spreads) if self.spreads else None,
            "minimum_spread": min(self.spreads) if self.spreads else None,
            "maximum_spread": max(self.spreads) if self.spreads else None,
        }


class TickRecorder:
    def __init__(
        self, storage: ParquetTickStorage, known_epics: set[str], flush_interval: float = 10
    ) -> None:
        self.storage, self.known_epics, self.flush_interval = storage, known_epics, flush_interval
        self.stats = RecorderStats()
        self.latest: dict[str, Tick] = {}
        self._stop = asyncio.Event()

    async def record_quote(
        self,
        *,
        epic: str,
        bid: object,
        ask: object,
        exchange_timestamp: datetime | None,
        bid_quantity: object = None,
        ask_quantity: object = None,
    ) -> Tick | None:
        self.stats.received += 1
        try:
            if epic not in self.known_epics:
                raise ValueError("unknown epic")
            if exchange_timestamp is None:
                raise ValueError("missing timestamp")
            tick = Tick.from_quote(
                epic=epic,
                bid=Decimal(str(bid)),
                ask=Decimal(str(ask)),
                exchange_timestamp=exchange_timestamp,
                bid_quantity=Decimal(str(bid_quantity)) if bid_quantity is not None else None,
                ask_quantity=Decimal(str(ask_quantity)) if ask_quantity is not None else None,
            )
        except (ValueError, TypeError, ArithmeticError) as exc:
            self.stats.rejected += 1
            log.warning("tick_rejected epic=%s reason=%s", epic, exc)
            return None
        previous = self.stats.last_by_epic.get(epic)
        if previous:
            self.stats.max_gap_seconds = max(
                self.stats.max_gap_seconds, (tick.received_timestamp - previous).total_seconds()
            )
        self.stats.last_by_epic[epic] = tick.received_timestamp
        self.stats.spreads.append(float(tick.spread_absolute))
        # Bound stats memory without altering stored raw ticks.
        if len(self.stats.spreads) > 100_000:
            self.stats.spreads = self.stats.spreads[-50_000:]
        self.latest[epic] = tick
        self.stats.stored += await self.storage.append(tick)
        return tick

    async def periodic_flush(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.flush_interval)
            except TimeoutError:
                self.stats.stored += await self.storage.flush()

    async def close(self) -> None:
        self._stop.set()
        self.stats.stored += await self.storage.flush()
        log.info("shutdown_summary %s", self.stats.summary())
