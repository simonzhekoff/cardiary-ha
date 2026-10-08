"""Client for the API behind web.car-diary.net.

Car Diary publishes no API; this talks to the one its own web app uses, so
any of it can change without notice. Read-only on purpose.
"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import API_URL, CLIENT_VERSION


class CarDiaryError(Exception):
    """The API could not be reached or answered with an error."""


class CarDiaryAuthError(CarDiaryError):
    """The credentials or the token were rejected."""


class CarDiaryClient:
    """Thin wrapper around the endpoints the integration reads."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str | None = None,
        currency: str = "eur",
        mileage_unit: str = "km",
    ) -> None:
        self._session = session
        self._token = token
        self._currency = currency
        self._mileage_unit = mileage_unit

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Exchange credentials for the user record, which carries the token."""
        user = await self._request(
            "POST",
            "/api/login",
            json={"email": email, "password": password, "source": "web"},
            auth=False,
        )
        if not isinstance(user, dict) or not user.get("api_token"):
            # Names only, the values may be personal.
            shape = sorted(user) if isinstance(user, dict) else type(user).__name__
            raise CarDiaryError(f"Login answered without a token: {shape}")
        self._token = user["api_token"]
        return user

    async def cars(self) -> list[dict[str, Any]]:
        return await self._list("/api/user-cars")

    async def refuels(self) -> list[dict[str, Any]]:
        return await self._list("/api/refuels")

    async def repairs(self) -> list[dict[str, Any]]:
        return await self._list("/api/repairs")

    async def taxes(self) -> list[dict[str, Any]]:
        return await self._list("/api/taxes")

    async def reminders(self) -> list[dict[str, Any]]:
        return await self._list("/api/reminders")

    async def _list(self, path: str) -> list[dict[str, Any]]:
        body = await self._request("GET", path)
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise CarDiaryError(f"{path} did not return a list")
        return data

    async def _request(
        self, method: str, path: str, *, json: Any = None, auth: bool = True
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "App-Platform": "web",
            "App-Client-Version": CLIENT_VERSION,
            "App-Currency": self._currency,
            "App-Language": "en",
            "App-Volume-Unit": "l",
            "App-Mileage-Type": self._mileage_unit,
        }
        if auth:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with asyncio.timeout(30):
                async with self._session.request(
                    method, f"{API_URL}{path}", json=json, headers=headers
                ) as resp:
                    # A wrong password comes back as 400/401/422 depending on
                    # the field; on the login call all of them mean "rejected".
                    if resp.status == 401 or (not auth and resp.status in (400, 403, 422)):
                        raise CarDiaryAuthError(f"{path}: HTTP {resp.status}")
                    if resp.status >= 400:
                        raise CarDiaryError(f"{path}: HTTP {resp.status}")
                    return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise CarDiaryError(f"{path}: {err}") from err
