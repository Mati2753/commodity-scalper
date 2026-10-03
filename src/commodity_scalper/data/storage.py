"""Bounded, atomic buffered Parquet persistence."""

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from commodity_scalper.data.tick import Tick

log = logging.getLogger(__name__)


class ParquetTickStorage:
    def __init__(self, root: Path, flush_ticks: int = 1000) -> None:
        self.root, self.flush_ticks = root, flush_ticks
        self._buffers: dict[str, list[Tick]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def append(self, tick: Tick) -> int:
        async with self._lock:
            self._buffers[tick.epic].append(tick)
            if sum(map(len, self._buffers.values())) >= self.flush_ticks:
                return self._flush_locked()
        return 0

    async def flush(self) -> int:
        async with self._lock:
            return self._flush_locked()

    def _flush_locked(self) -> int:
        total = 0
        for epic, ticks in list(self._buffers.items()):
            if not ticks:
                continue
            groups: dict[str, list[Tick]] = defaultdict(list)
            for tick in ticks:
                groups[tick.received_timestamp.date().isoformat()].append(tick)
            for date, dated_ticks in groups.items():
                folder = self.root / self._safe_epic(epic) / f"date={date}"
                folder.mkdir(parents=True, exist_ok=True)
                stem = f"ticks-{datetime.now().strftime('%H%M%S%f')}-{uuid.uuid4().hex[:8]}"
                temporary, final = folder / f".{stem}.parquet.tmp", folder / f"{stem}.parquet"
                table = pa.Table.from_pylist([self._row(t) for t in dated_ticks])
                pq.write_table(table, temporary, compression="zstd")
                temporary.replace(final)
                total += len(dated_ticks)
                log.info("storage_flush epic=%s ticks=%d file=%s", epic, len(dated_ticks), final)
            self._buffers[epic].clear()
        return total

    @staticmethod
    def _safe_epic(epic: str) -> str:
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in epic)

    @staticmethod
    def _row(t: Tick) -> dict[str, object]:
        data = t.model_dump()
        for field in (
            "bid",
            "ask",
            "bid_quantity",
            "ask_quantity",
            "mid",
            "spread_absolute",
            "spread_bps",
        ):
            data[field] = float(data[field]) if data[field] is not None else None
        return data
