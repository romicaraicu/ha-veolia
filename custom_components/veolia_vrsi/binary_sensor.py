"""Senzori binari Veolia VRSI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import VeoliaConfigEntry
from .entity import VeoliaEntity
from .parser import LocationData, iso


@dataclass(frozen=True, kw_only=True)
class VeoliaBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[LocationData, date], bool]
    attrs_fn: Callable[[LocationData, date], dict[str, Any]]


BINARY_SENSORS: tuple[VeoliaBinaryDescription, ...] = (
    VeoliaBinaryDescription(
        key="perioada_index_activa",
        icon="mdi:counter",
        is_on_fn=lambda d, t: d.reading_open,
        attrs_fn=lambda d, t: {
            "contor_smart": d.is_smart,
            "inceput": iso(d.reading_start),
            "sfarsit": iso(d.reading_end),
        },
    ),
    VeoliaBinaryDescription(
        key="factura_restanta",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d, t: d.overdue_amount(t) > 0,
        attrs_fn=lambda d, t: {
            "restant": d.overdue_amount(t),
            "urmatoarea_scadenta": iso(d.next_due_date(t)),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VeoliaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        VeoliaBinarySensor(coordinator, code, description)
        for code in coordinator.data
        for description in BINARY_SENSORS
    )


class VeoliaBinarySensor(VeoliaEntity, BinarySensorEntity):
    entity_description: VeoliaBinaryDescription

    def __init__(self, coordinator, code: str, description: VeoliaBinaryDescription) -> None:
        super().__init__(coordinator, code, description.key, "binary_sensor")
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data = self.location
        return None if data is None else self.entity_description.is_on_fn(data, dt_util.now().date())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.location
        return {} if data is None else self.entity_description.attrs_fn(data, dt_util.now().date())
