"""Phase 1 command-line application. There are deliberately no order methods."""

import asyncio
import contextlib
import logging
import signal
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

from commodity_scalper.analysis.feasibility import create_report
from commodity_scalper.capital.client import CapitalClient
from commodity_scalper.capital.markets import discover, load_instruments, save_instruments
from commodity_scalper.capital.websocket import MarketStreamer
from commodity_scalper.config import Settings
from commodity_scalper.data.recorder import TickRecorder
from commodity_scalper.data.storage import ParquetTickStorage
from commodity_scalper.utils.logging import configure_logging

app = typer.Typer(
    no_args_is_help=True,
    help="Capital.com DEMO Phase 1 research infrastructure (never places orders).",
)
console = Console()
log = logging.getLogger(__name__)


def settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        console.print(f"[red]Configuration error: {exc}[/red]")
        raise typer.Exit(2) from exc


def market_table(label: str, market: object) -> Table:
    m = market
    table = Table(title=label)
    table.add_column("Field")
    table.add_column("Value")
    spread = (
        m.snapshot.offer - m.snapshot.bid
        if m.snapshot.bid is not None and m.snapshot.offer is not None
        else "UNKNOWN"
    )
    for key, value in (
        ("Epic", m.instrument.epic),
        ("Status", m.snapshot.marketStatus),
        ("Bid", m.snapshot.bid),
        ("Ask", m.snapshot.offer),
        ("Spread", spread),
        (
            "Min deal size",
            m.dealingRules.minDealSize.value if m.dealingRules.minDealSize else "UNKNOWN",
        ),
        ("Lot size", m.instrument.lotSize),
        ("Margin factor", f"{m.instrument.marginFactor} {m.instrument.marginFactorUnit or ''}"),
        ("Streaming", "YES" if m.instrument.streamingPricesAvailable else "NO"),
    ):
        table.add_row(key, str(value))
    return table


@app.command("discover-markets")
def discover_markets() -> None:
    """Authenticate, search dynamically, resolve unambiguous instruments, and persist details."""
    config = settings()
    config.require_credentials()
    configure_logging(
        [config.capital_api_key.get_secret_value(), config.capital_api_password.get_secret_value()]
    )

    async def run() -> None:
        async with CapitalClient(config) as client:
            await client.authenticate()
            markets, candidates = await discover(client)
            for label, values in candidates.items():
                console.print(
                    f"[bold]{label} candidates:[/bold] "
                    + ", ".join(f"{c.instrumentName} ({c.epic})" for c in values)
                )
            save_instruments(config.instruments_file, markets)
            for label, market in markets.items():
                console.print(market_table(label, market))

    asyncio.run(run())


@app.command()
def feasibility() -> None:
    """Analyze saved, current API-derived specifications without inventing missing values."""
    config = settings()
    configure_logging()
    markets = load_instruments(config.instruments_file)
    if not markets:
        console.print("[red]No instruments saved. Run discover-markets first.[/red]")
        raise typer.Exit(2)
    report = create_report(markets, config.reports_dir / "feasibility.json")
    table = Table(title="Minimum-position feasibility (USD)")
    for column in (
        "Commodity",
        "Balance",
        "Min size",
        "Notional",
        "Margin",
        "Spread cost",
        "Sufficient",
        "Margin %",
    ):
        table.add_column(column)
    for market in report["markets"]:
        for row in market["balances"]:
            table.add_row(
                market["commodity"],
                f"${row['balance_usd']}",
                market["minimum_trade_size"],
                market["approximate_notional_usd"],
                market["estimated_initial_margin_usd"],
                market["current_spread_cost_usd"],
                str(row["sufficient"]),
                row["margin_utilization_percent"],
            )
    console.print(table)
    console.print(f"Saved {config.reports_dir / 'feasibility.json'}")


@app.command("stream")
def stream_ticks(
    minutes: float | None = typer.Option(None, min=0.01),
    instrument: str | None = typer.Option(None, help="GOLD, WTI, NATURAL_GAS, or a selected EPIC"),
    output_dir: Path | None = None,
) -> None:
    """Stream selected raw quotes until duration or Ctrl+C and always flush."""
    config = settings()
    config.require_credentials()
    configure_logging(
        [config.capital_api_key.get_secret_value(), config.capital_api_password.get_secret_value()]
    )
    markets = load_instruments(config.instruments_file)
    if not markets:
        console.print("[red]No selected instruments; run discover-markets first.[/red]")
        raise typer.Exit(2)
    if instrument:
        wanted = instrument.upper()
        markets = {
            k: v for k, v in markets.items() if k == wanted or v.instrument.epic.upper() == wanted
        }
        if not markets:
            console.print(f"[red]Unknown selected instrument: {instrument}[/red]")
            raise typer.Exit(2)

    async def run() -> None:
        storage = ParquetTickStorage(output_dir or config.ticks_dir, config.capital_flush_ticks)
        epics = {m.instrument.epic for m in markets.values()}
        recorder = TickRecorder(storage, epics, config.capital_flush_interval_seconds)
        async with CapitalClient(config) as client:
            await client.authenticate()
            streamer = MarketStreamer(client, recorder, sorted(epics))
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                with contextlib.suppress(NotImplementedError):
                    loop.add_signal_handler(sig, streamer.stop.set)
            flush_task = asyncio.create_task(recorder.periodic_flush())

            async def display() -> None:
                with Live(console=console, refresh_per_second=2) as live:
                    while not streamer.stop.is_set():
                        table = Table(title="Capital.com DEMO raw ticks")
                        for col in ("Instrument", "Bid", "Ask", "Spread", "Ticks", "Last update"):
                            table.add_column(col)
                        for label, market in markets.items():
                            tick = recorder.latest.get(market.instrument.epic)
                            table.add_row(
                                label,
                                str(tick.bid if tick else "—"),
                                str(tick.ask if tick else "—"),
                                str(tick.spread_absolute if tick else "—"),
                                str(recorder.stats.received),
                                str(tick.received_timestamp if tick else "—"),
                            )
                        live.update(table)
                        await asyncio.sleep(0.5)

            display_task = asyncio.create_task(display())
            try:
                await streamer.run(minutes * 60 if minutes else None)
            finally:
                await streamer.close()
                await recorder.close()
                flush_task.cancel()
                display_task.cancel()
                await asyncio.gather(flush_task, display_task, return_exceptions=True)
                console.print(recorder.stats.summary())

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run())


if __name__ == "__main__":
    app()
