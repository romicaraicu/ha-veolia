"""Entitate de bază Veolia VRSI (un dispozitiv per loc de consum)."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, MANUFACTURER, PORTAL_URL
from .coordinator import VeoliaCoordinator
from .parser import LocationData


class VeoliaEntity(CoordinatorEntity[VeoliaCoordinator]):
    """Entitate legată de un loc de consum."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VeoliaCoordinator, code: str, key: str, platform: str) -> None:
        super().__init__(coordinator)
        self._code = code
        self._attr_translation_key = key
        self._attr_unique_id = f"{code}_{key}"
        # Entity ID previzibil, folosit și de dashboard: <platform>.veolia_vrsi_<cod>_<cheie>
        self.entity_id = f"{platform}.{DOMAIN}_{slugify(code)}_{key}"
        data = coordinator.data.get(code)
        address = data.address if data else code
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, code)},
            name=f"Veolia {address}",
            manufacturer=MANUFACTURER,
            model="Loc de consum",
            serial_number=code,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=PORTAL_URL,
        )

    @property
    def location(self) -> LocationData | None:
        return (self.coordinator.data or {}).get(self._code)

    @property
    def available(self) -> bool:
        return super().available and self.location is not None
