from datetime import UTC, datetime

import pyarrow.parquet as pq
import pytest

from commodity_scalper.data.storage import ParquetTickStorage
from commodity_scalper.data.tick import Tick


@pytest.mark.asyncio
async def test_parquet_persistence(tmp_path):
    storage = ParquetTickStorage(tmp_path, flush_ticks=2)
    for price in (10, 11):
        await storage.append(
            Tick.from_quote(
                epic="GOLD/TEST", bid=price, ask=price + 1, exchange_timestamp=datetime.now(UTC)
            )
        )
    files = list(tmp_path.glob("GOLD_TEST/date=*/*.parquet"))
    assert len(files) == 1
    table = pq.read_table(files[0])
    assert table.num_rows == 2 and {"bid", "ask", "spread_bps"} <= set(table.column_names)
