from commodity_scalper.capital.websocket import parse_market_update


def test_market_update_parsing():
    quote = parse_market_update(
        {
            "destination": "marketData.subscribe",
            "payload": {
                "epic": "X",
                "bid": 1,
                "ofr": 2,
                "timestamp": 1700000000000,
                "bidQty": 3,
                "ofrQty": 4,
            },
        }
    )
    assert quote is not None and quote["ask"] == 2 and quote["exchange_timestamp"] is not None


def test_non_quote_is_ignored():
    assert parse_market_update({"destination": "ping", "payload": {}}) is None
