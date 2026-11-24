"""Buton de actualizare Veolia VRSI."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VeoliaConfigEntry
from .entity import VeoliaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VeoliaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(VeoliaRefreshButton(coordinator, code) for code in coordinator.data)


class VeoliaRefreshButton(VeoliaEntity, ButtonEntity):
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator, code: str) -> None:
        super().__init__(coordinator, code, "actualizare", "button")

    @property
    def available(self) -> bool:
        # butonul rămâne disponibil și după o actualizare eșuată: e calea de reîncercare
        return self.location is not None

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
