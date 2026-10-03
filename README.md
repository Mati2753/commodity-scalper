# Commodity Micro-Scalper — Phase 1

> **PHASE 1 DOES NOT PLACE TRADES.** It contains no order-placement command or execution client. CFDs are leveraged, high-risk products; this research software never guarantees profit, and `NO_TRADE` is a valid future decision.

This Python 3.12+ local application authenticates only to Capital.com's **demo** REST API, inspects the selected account, dynamically discovers Gold, WTI crude oil, and Natural Gas instruments available to that account, downloads their complete specifications, subscribes to their market-data WebSocket, and preserves raw bid/ask ticks in bounded, atomic Parquet batches. It also produces a deliberately conservative small-balance feasibility report. It does **not** trade, predict, backtest, or implement ML.

The implementation follows the [official Capital.com API specification](https://open-api.capital.com/): sessions use `POST /api/v1/session`, market search uses `GET /api/v1/markets?searchTerm=...`, details use `GET /api/v1/markets/{epic}`, REST keepalive uses `GET /api/v1/ping`, and streaming uses `wss://api-streaming-capital.backend-capital.com/connect`. Instrument EPICs are never guessed or embedded.

## Install

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Generate a demo API key in the Capital.com web platform under **Settings → API integrations → Generate API key** (2FA may be required), and retain the key when shown. Put these values in `.env`:

- `CAPITAL_ENV=demo` — required; `live` fails closed.
- `CAPITAL_API_KEY` — generated API key.
- `CAPITAL_IDENTIFIER` — demo-account login/email.
- `CAPITAL_API_PASSWORD` — the custom password assigned to the API key, not a value to commit.
- `CAPITAL_ACCOUNT_ID` — optional demo financial account ID; when set, the client selects it after login.
- `PHASE1_ALLOW_LIVE=false` — must remain false; true is rejected rather than acting as an override.

`.env`, tokens, API keys, and generated market data are ignored by Git. Logs redact configured credentials and common credential fields. Do not paste logs containing upstream payloads without inspecting them.

## Commands

```bash
# Search all configured terms, display candidates, require an unambiguous match,
# fetch details, and atomically write config/instruments.json
python -m commodity_scalper.cli discover-markets

# Stream all three until Ctrl+C, or limit the run/selection
python -m commodity_scalper.cli stream --minutes 10
python -m commodity_scalper.cli stream --instrument GOLD --minutes 30
python -m commodity_scalper.cli stream --output-dir ./data/ticks

# Analyze the last dynamically fetched rules at $3 ... $500
python -m commodity_scalper.cli feasibility

# Offline quality gates
pytest
ruff check .
mypy src
```

Run discovery immediately before feasibility when current quotes/rules matter. Selection deliberately stops on tied candidates rather than silently choosing the wrong contract. Inspect candidates and narrow the account's available markets if this occurs.

## Data and reliability

```text
config/instruments.json                  selected API specifications
data/ticks/<sanitized-epic>/date=YYYY-MM-DD/ticks-*.parquet
data/reports/feasibility.json            machine-readable balance analysis
```

Each raw row retains source and UTC receive timestamps, EPIC, bid, ask/offer, optional quantities, mid, absolute spread, and spread basis points. Invalid/nonpositive/crossed/unknown/missing-time quotes are logged and rejected. Buffers flush by row count, periodically, and during graceful shutdown. Files are written to a temporary name then atomically renamed; memory is bounded by flush limits. Summary metrics include received/stored/rejected ticks, reconnections, maximum receive gap, and spread statistics.

REST calls have timeouts, limited exponential retries, `Retry-After` handling, and one automatic reauthentication on 401. Streaming has protocol and application keepalives, exponential reconnect, and resubscription. Ctrl+C requests shutdown and flushes remaining rows.

Feasibility calculates notional/spread cost only where price, minimum size, lot size, and USD contract currency establish the needed semantics. Percentage/decimal margin factors are handled explicitly. Otherwise it says **UNKNOWN — additional contract information required**, never manufacturing an answer that makes a $3 account appear viable. These remain estimates: verify contract sizing, currency conversion, margin tiers, and broker rules manually.

## Testing and boundaries

Tests use mocked HTTP and local models; no test contacts Capital.com. `config/instruments.json` begins empty because actual instruments depend on the authenticated account. Consequently authentication, discovery results, WebSocket receipt/subscription, and current feasibility require manual verification with demo credentials.

Future phases may add feature engineering, an event-driven backtester, regime detection, short-horizon models (5/10/20/30/60/180 seconds), expected-value evaluation, and only later demo execution/risk controls. Model evaluation must use chronological train/validation/test splits, walk-forward and truly out-of-sample tests, actual bid/ask prices, spread, slippage and latency assumptions, and strict prevention of look-ahead leakage. Historical fit alone is not evidence of a successful strategy.
