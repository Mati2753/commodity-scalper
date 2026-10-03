"""Async, retrying, demo-only Capital.com REST client."""

import asyncio
import logging
from typing import Any

import httpx

from commodity_scalper.capital.auth import SessionTokens
from commodity_scalper.config import Settings

log = logging.getLogger(__name__)


class CapitalAPIError(RuntimeError):
    pass


class AuthenticationError(CapitalAPIError):
    pass


class CapitalClient:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        settings.require_credentials()
        self.settings = settings
        self.tokens: SessionTokens | None = None
        self.http = httpx.AsyncClient(
            base_url=settings.rest_url,
            timeout=settings.capital_http_timeout_seconds,
            transport=transport,
        )
        self._auth_lock = asyncio.Lock()

    async def __aenter__(self) -> "CapitalClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self.http.aclose()

    async def authenticate(self) -> dict[str, Any]:
        async with self._auth_lock:
            response = await self.http.post(
                "/api/v1/session",
                headers={"X-CAP-API-KEY": self.settings.capital_api_key.get_secret_value()},
                json={
                    "identifier": self.settings.capital_identifier,
                    "password": self.settings.capital_api_password.get_secret_value(),
                    "encryptedPassword": False,
                },
            )
            if response.status_code != 200:
                raise AuthenticationError(
                    f"Demo authentication failed (HTTP {response.status_code})"
                )
            cst, security = response.headers.get("CST"), response.headers.get("X-SECURITY-TOKEN")
            if not cst or not security:
                raise AuthenticationError("Authentication response omitted session tokens")
            body = response.json()
            self.tokens = SessionTokens(cst, security, body.get("currentAccountId"))
            log.info(
                "Demo authentication succeeded; account=%s", body.get("currentAccountId", "unknown")
            )
            if self.settings.capital_account_id and self.settings.capital_account_id != body.get(
                "currentAccountId"
            ):
                await self._request(
                    "PUT",
                    "/api/v1/session",
                    json={"accountId": self.settings.capital_account_id},
                    retry_auth=False,
                )
                self.tokens.account_id = self.settings.capital_account_id
            return body

    def _headers(self) -> dict[str, str]:
        if not self.tokens:
            return {"X-CAP-API-KEY": self.settings.capital_api_key.get_secret_value()}
        return {
            "X-CAP-API-KEY": self.settings.capital_api_key.get_secret_value(),
            "CST": self.tokens.cst,
            "X-SECURITY-TOKEN": self.tokens.security_token,
        }

    async def _request(
        self, method: str, path: str, *, retry_auth: bool = True, **kwargs: Any
    ) -> dict[str, Any]:
        if not self.tokens:
            await self.authenticate()
        for attempt in range(self.settings.capital_max_retries + 1):
            try:
                response = await self.http.request(method, path, headers=self._headers(), **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == self.settings.capital_max_retries:
                    raise CapitalAPIError("Capital.com request failed after retries") from exc
                await asyncio.sleep(min(2**attempt, 8))
                continue
            if response.status_code == 401 and retry_auth and attempt == 0:
                self.tokens = None
                await self.authenticate()
                continue
            if (response.status_code == 429 or 500 <= response.status_code < 600) and (
                attempt < self.settings.capital_max_retries
            ):
                delay = float(response.headers.get("Retry-After", min(2**attempt, 8)))
                await asyncio.sleep(delay)
                continue
            if response.is_error:
                raise CapitalAPIError(
                    f"Capital.com API error HTTP {response.status_code}: {response.text[:300]}"
                )
            return response.json() if response.content else {}
        raise CapitalAPIError("Request retries exhausted")

    async def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self._request("GET", path, **kwargs)

    async def ping(self) -> None:
        await self.get("/api/v1/ping")
