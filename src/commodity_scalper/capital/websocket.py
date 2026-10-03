"""Capital.com market stream with application ping and bounded reconnect."""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import websockets

from commodity_scalper.capital.client import CapitalClient
from commodity_scalper.config import STREAM_URL
from commodity_scalper.data.recorder import TickRecorder

log = logging.getLogger(__name__)


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / (1000 if float(value) > 10_000_000_000 else 1)
        return datetime.fromtimestamp(seconds, UTC)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_market_update(message: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("destination") not in {"marketData.subscribe", "marketData"}:
        return None
    payload = message.get("payload", {})
    epic = payload.get("epic")
    bid, ask = payload.get("bid"), payload.get("ofr", payload.get("offer", payload.get("ask")))
    if epic is None or bid is None or ask is None:
        return None
    return {
        "epic": epic,
        "bid": bid,
        "ask": ask,
        "exchange_timestamp": _timestamp(
            payload.get("timestamp") or payload.get("updateTime") or payload.get("snapshotTime")
        ),
        "bid_quantity": payload.get("bidQty", payload.get("bidQuantity")),
        "ask_quantity": payload.get("ofrQty", payload.get("askQuantity")),
    }


class MarketStreamer:
    def __init__(self, client: CapitalClient, recorder: TickRecorder, epics: list[str]) -> None:
        self.client, self.recorder, self.epics = client, recorder, epics
        self.stop = asyncio.Event()

    def _message(self, destination: str, payload: dict[str, Any] | None = None) -> str:
        assert self.client.tokens
        value = {
            "destination": destination,
            "correlationId": uuid.uuid4().hex,
            "cst": self.client.tokens.cst,
            "securityToken": self.client.tokens.security_token,
        }
        if payload is not None:
            value["payload"] = payload
        return json.dumps(value)

    async def run(self, duration_seconds: float | None = None) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + duration_seconds if duration_seconds else None
        attempt = 0
        while not self.stop.is_set() and (deadline is None or loop.time() < deadline):
            if not self.client.tokens:
                await self.client.authenticate()
            try:
                async with websockets.connect(
                    STREAM_URL, ping_interval=20, ping_timeout=20, close_timeout=10
                ) as websocket:
                    log.info("websocket_connected epics=%s", ",".join(self.epics))
                    await websocket.send(
                        self._message("marketData.subscribe", {"epics": self.epics})
                    )
                    attempt = 0
                    next_app_ping = loop.time() + 300
                    while not self.stop.is_set() and (deadline is None or loop.time() < deadline):
                        if loop.time() >= next_app_ping:
                            await websocket.send(self._message("ping"))
                            await self.client.ping()
                            next_app_ping = loop.time() + 300
                        timeout = min(30.0, max(0.1, deadline - loop.time())) if deadline else 30.0
                        try:
                            raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                        except TimeoutError:
                            continue
                        message = json.loads(raw)
                        quote = parse_market_update(message)
                        if quote:
                            await self.recorder.record_quote(**quote)
                        elif message.get("status") == "ERROR":
                            log.error(
                                "websocket_message_error destination=%s", message.get("destination")
                            )
            except (OSError, websockets.WebSocketException, json.JSONDecodeError) as exc:
                if self.stop.is_set():
                    break
                attempt += 1
                self.recorder.stats.reconnections += 1
                delay = min(2 ** min(attempt, 5), 30)
                log.warning(
                    "websocket_reconnect attempt=%d delay=%d error=%s",
                    attempt,
                    delay,
                    type(exc).__name__,
                )
                await asyncio.sleep(delay)

    async def close(self) -> None:
        self.stop.set()
