"""Polls Car Diary and groups everything by car."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CarDiaryAuthError, CarDiaryClient, CarDiaryError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type CarDiaryConfigEntry = ConfigEntry[CarDiaryCoordinator]


def parse_date(value: Any) -> date | None:
    """The API writes dates as YYYY-MM-DD, sometimes with a time after it."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def to_float(value: Any) -> float | None:
    """Prices arrive as strings, amounts as numbers, either may be null."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class CarData:
    """One car with its records, newest first."""

    car: dict[str, Any]
    refuels: list[dict[str, Any]] = field(default_factory=list)
    repairs: list[dict[str, Any]] = field(default_factory=list)
    taxes: list[dict[str, Any]] = field(default_factory=list)
    reminders: list[dict[str, Any]] = field(default_factory=list)

    @property
    def last_refuel(self) -> dict[str, Any] | None:
        return self.refuels[0] if self.refuels else None

    @property
    def last_repair(self) -> dict[str, Any] | None:
        return self.repairs[0] if self.repairs else None

    def latest_tax(self, tax_type: str) -> dict[str, Any] | None:
        """The record of this kind that expires last, i.e. the current one."""
        best = None
        for tax in self.taxes:
            if tax.get("type") != tax_type or parse_date(tax.get("expires_at")) is None:
                continue
            if best is None or tax["expires_at"] > best["expires_at"]:
                best = tax
        return best

    def upcoming_reminders(self, today: date) -> list[dict[str, Any]]:
        """Active date reminders from today on, soonest first."""
        found = [
            r
            for r in self.reminders
            if r.get("is_active")
            and (when := parse_date(r.get("next_remind_date"))) is not None
            and when >= today
        ]
        return sorted(found, key=lambda r: r["next_remind_date"])

    def spent_since(self, start: date, kinds: tuple[str, ...]) -> float:
        total = 0.0
        for kind in kinds:
            for row in getattr(self, kind):
                when = parse_date(row.get("log_date"))
                if when is not None and when >= start:
                    total += to_float(row.get("final_price")) or 0.0
        return round(total, 2)


class CarDiaryCoordinator(DataUpdateCoordinator[dict[int, CarData]]):
    """One poll fetches everything; the API returns whole lists, unfiltered."""

    config_entry: CarDiaryConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: CarDiaryConfigEntry, client: CarDiaryClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, CarData]:
        try:
            cars, refuels, repairs, taxes, reminders = await asyncio.gather(
                self.client.cars(),
                self.client.refuels(),
                self.client.repairs(),
                self.client.taxes(),
                self.client.reminders(),
            )
        except CarDiaryAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CarDiaryError as err:
            raise UpdateFailed(str(err)) from err

        data = {car["id"]: CarData(car) for car in cars}
        # Records of cars that were deleted in the app still come back; they
        # have no car to hang from and are dropped here.
        for kind, rows in (
            ("refuels", refuels),
            ("repairs", repairs),
            ("taxes", taxes),
            ("reminders", reminders),
        ):
            for row in rows:
                if (car := data.get(row.get("user_car_id"))) is not None:
                    getattr(car, kind).append(row)
        for car in data.values():
            for kind in ("refuels", "repairs"):
                getattr(car, kind).sort(
                    key=lambda r: (r.get("log_date") or "", r.get("id") or 0),
                    reverse=True,
                )
        return data

    @staticmethod
    def today() -> date:
        return dt_util.now().date()
