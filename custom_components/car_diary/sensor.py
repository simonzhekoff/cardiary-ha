"""Sensors for each car in Car Diary."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TAX_TYPES
from .coordinator import (
    CarData,
    CarDiaryConfigEntry,
    CarDiaryCoordinator,
    parse_date,
    to_float,
)

MONEY = "money"  # replaced by the Home Assistant currency at setup


@dataclass(frozen=True, kw_only=True)
class CarDiarySensorDescription(SensorEntityDescription):
    """A sensor computed from one car's data."""

    value_fn: Callable[[CarData, date], StateType | date]
    attrs_fn: Callable[[CarData, date], dict[str, Any]] | None = None
    # Sensors whose source record a car may simply not have are only created
    # once it does, instead of sitting there as "unknown" forever.
    exists_fn: Callable[[CarData], bool] = lambda car: True


def _refuel(car: CarData, key: str) -> Any:
    return (car.last_refuel or {}).get(key)


def _refuel_attrs(car: CarData, today: date) -> dict[str, Any]:
    refuel = car.last_refuel or {}
    return {
        "station": refuel.get("gas_station"),
        "fuel": refuel.get("fuel"),
        "mileage": refuel.get("mileage"),
        "distance_since_previous": refuel.get("mileage_difference"),
        "full_tank": bool(refuel.get("full_tank")),
    }


def _days_left(when: date | None, today: date) -> int | None:
    return (when - today).days if when else None


def _tax_description(tax_type: str) -> CarDiarySensorDescription:
    def value(car: CarData, today: date) -> date | None:
        return parse_date((car.latest_tax(tax_type) or {}).get("expires_at"))

    def attrs(car: CarData, today: date) -> dict[str, Any]:
        tax = car.latest_tax(tax_type) or {}
        when = parse_date(tax.get("expires_at"))
        return {
            "days_left": _days_left(when, today),
            "expired": when is not None and when < today,
            "paid_on": tax.get("log_date"),
            "price": tax.get("final_price"),
            "note": tax.get("note"),
        }

    return CarDiarySensorDescription(
        key=f"{tax_type}_expires",
        translation_key=f"{tax_type}_expires",
        device_class=SensorDeviceClass.DATE,
        value_fn=value,
        attrs_fn=attrs,
        exists_fn=lambda car: car.latest_tax(tax_type) is not None,
    )


def _next_reminder(car: CarData, today: date) -> dict[str, Any]:
    upcoming = car.upcoming_reminders(today)
    return upcoming[0] if upcoming else {}


def _reminder_attrs(car: CarData, today: date) -> dict[str, Any]:
    upcoming = car.upcoming_reminders(today)
    first = upcoming[0] if upcoming else {}
    return {
        "reminder": first.get("content"),
        "days_left": _days_left(parse_date(first.get("next_remind_date")), today),
        "repeats": first.get("repeat_date"),
        "upcoming": [
            {"date": r["next_remind_date"], "reminder": r.get("content")}
            for r in upcoming[:10]
        ],
    }


SENSORS: tuple[CarDiarySensorDescription, ...] = (
    CarDiarySensorDescription(
        key="mileage",
        translation_key="mileage",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda car, today: car.car.get("mileage"),
    ),
    CarDiarySensorDescription(
        key="average_consumption",
        translation_key="average_consumption",
        native_unit_of_measurement="L/100 km",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda car, today: to_float(car.car.get("consumption")),
    ),
    CarDiarySensorDescription(
        key="last_refuel",
        translation_key="last_refuel",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda car, today: parse_date(_refuel(car, "log_date")),
        attrs_fn=_refuel_attrs,
    ),
    CarDiarySensorDescription(
        key="last_refuel_volume",
        translation_key="last_refuel_volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=2,
        value_fn=lambda car, today: to_float(_refuel(car, "amount")),
    ),
    CarDiarySensorDescription(
        key="last_refuel_cost",
        translation_key="last_refuel_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=MONEY,
        suggested_display_precision=2,
        value_fn=lambda car, today: to_float(_refuel(car, "final_price")),
    ),
    CarDiarySensorDescription(
        key="last_fuel_price",
        translation_key="last_fuel_price",
        native_unit_of_measurement=f"{MONEY}/L",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        # Derived from the cost, so it is in the same currency as the cost.
        value_fn=lambda car, today: (
            round(cost / volume, 3)
            if (cost := to_float(_refuel(car, "final_price")))
            and (volume := to_float(_refuel(car, "amount")))
            else None
        ),
    ),
    CarDiarySensorDescription(
        key="fuel_cost_this_month",
        translation_key="fuel_cost_this_month",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=MONEY,
        suggested_display_precision=2,
        value_fn=lambda car, today: car.spent_since(today.replace(day=1), ("refuels",)),
    ),
    CarDiarySensorDescription(
        key="expenses_this_year",
        translation_key="expenses_this_year",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=MONEY,
        suggested_display_precision=2,
        value_fn=lambda car, today: car.spent_since(
            today.replace(month=1, day=1), ("refuels", "repairs", "taxes")
        ),
        attrs_fn=lambda car, today: {
            kind: car.spent_since(today.replace(month=1, day=1), (kind,))
            for kind in ("refuels", "repairs", "taxes")
        },
    ),
    CarDiarySensorDescription(
        key="last_repair",
        translation_key="last_repair",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda car, today: parse_date((car.last_repair or {}).get("log_date")),
        attrs_fn=lambda car, today: {
            "name": (car.last_repair or {}).get("name"),
            "mileage": (car.last_repair or {}).get("mileage"),
            "price": (car.last_repair or {}).get("final_price"),
        },
        exists_fn=lambda car: car.last_repair is not None,
    ),
    CarDiarySensorDescription(
        key="next_reminder",
        translation_key="next_reminder",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda car, today: parse_date(
            _next_reminder(car, today).get("next_remind_date")
        ),
        attrs_fn=_reminder_attrs,
    ),
    CarDiarySensorDescription(
        key="warranty_until",
        translation_key="warranty_until",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda car, today: parse_date(car.car.get("warranty_until")),
        attrs_fn=lambda car, today: {
            "days_left": _days_left(parse_date(car.car.get("warranty_until")), today)
        },
        exists_fn=lambda car: parse_date(car.car.get("warranty_until")) is not None,
    ),
    *(_tax_description(tax_type) for tax_type in TAX_TYPES),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CarDiaryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    created: set[tuple[int, str]] = set()

    @callback
    def add_new() -> None:
        """Cars and records added in the app later show up without a reload."""
        new = []
        for car_id, car in coordinator.data.items():
            for description in SENSORS:
                if (car_id, description.key) in created or not description.exists_fn(car):
                    continue
                created.add((car_id, description.key))
                new.append(CarDiarySensor(coordinator, car_id, description))
        if new:
            async_add_entities(new)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class CarDiarySensor(CoordinatorEntity[CarDiaryCoordinator], SensorEntity):
    """One value of one car."""

    _attr_has_entity_name = True
    entity_description: CarDiarySensorDescription

    def __init__(
        self,
        coordinator: CarDiaryCoordinator,
        car_id: int,
        description: CarDiarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._car_id = car_id
        self._attr_unique_id = f"{car_id}_{description.key}"
        car = coordinator.data[car_id].car
        brand = (car.get("car_brand") or {}).get("name")
        model = (car.get("car_model") or {}).get("name")
        plate = car.get("reg_plate")
        name = " ".join(part for part in (brand, model) if part) or car.get("variant")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(car_id))},
            name=f"{name} ({plate})" if name and plate else name or plate or str(car_id),
            manufacturer=brand,
            model=car.get("variant") or model,
            serial_number=car.get("vin"),
            configuration_url="https://web.car-diary.net",
        )
        unit = description.native_unit_of_measurement
        if unit and MONEY in unit:
            self._attr_native_unit_of_measurement = unit.replace(
                MONEY, coordinator.hass.config.currency
            )
        if description.key == "mileage":
            self._attr_native_unit_of_measurement = (
                UnitOfLength.MILES
                if coordinator.hass.config.units.length_unit == UnitOfLength.MILES
                else UnitOfLength.KILOMETERS
            )

    @property
    def available(self) -> bool:
        return super().available and self._car_id in self.coordinator.data

    @property
    def native_value(self) -> StateType | date:
        return self.entity_description.value_fn(
            self.coordinator.data[self._car_id], self.coordinator.today()
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(
            self.coordinator.data[self._car_id], self.coordinator.today()
        )
