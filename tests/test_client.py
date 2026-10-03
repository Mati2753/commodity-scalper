import httpx
import pytest

from commodity_scalper.capital.client import CapitalClient
from commodity_scalper.config import Settings


@pytest.mark.asyncio
async def test_auth_and_headers_without_live_network():
    async def handler(request):
        assert request.url.host == "demo-api-capital.backend-capital.com"
        return httpx.Response(
            200,
            headers={"CST": "secret-a", "X-SECURITY-TOKEN": "secret-b"},
            json={"currentAccountId": "demo"},
        )

    config = Settings(
        _env_file=None, capital_api_key="key", capital_identifier="id", capital_api_password="pw"
    )
    async with CapitalClient(config, httpx.MockTransport(handler)) as client:
        await client.authenticate()
        assert "secret-a" not in repr(client.tokens)
