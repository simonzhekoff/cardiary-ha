"""Car Diary: mileage, fuel, documents and reminders from car-diary.net."""
from __future__ import annotations

from homeassistant.const import Platform, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CarDiaryClient
from .const import CONF_TOKEN
from .coordinator import CarDiaryConfigEntry, CarDiaryCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CarDiaryConfigEntry) -> bool:
    client = CarDiaryClient(
        async_get_clientsession(hass),
        entry.data[CONF_TOKEN],
        currency=hass.config.currency.lower(),
        mileage_unit="mi" if hass.config.units.length_unit == UnitOfLength.MILES else "km",
    )
    coordinator = CarDiaryCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CarDiaryConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
