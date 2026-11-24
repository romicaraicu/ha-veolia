"""DataUpdateCoordinator pentru Veolia VRSI."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VeoliaAuthError, VeoliaBlockedError, VeoliaBridgeClient, VeoliaError
from .const import CONF_LOCATIONS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS, DOMAIN
from .parser import LocationData, build_locations
from .statistics import async_import_statistics

_LOGGER = logging.getLogger(__name__)

ISSUE_WAF_BLOCKED = "waf_blocked"


class VeoliaCoordinator(DataUpdateCoordinator[dict[str, LocationData]]):
    """Cere snapshot-ul de la bridge și îl împarte pe locuri de consum."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: VeoliaBridgeClient) -> None:
        hours = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=timedelta(hours=hours),
        )
        self.api = api
        self.raw: dict[str, Any] = {}

    @property
    def selected_locations(self) -> list[str] | None:
        """Locurile alese de utilizator (None = toate)."""
        return self.config_entry.options.get(CONF_LOCATIONS) or None

    async def _async_update_data(self) -> dict[str, LocationData]:
        try:
            snapshot = await self.api.get_snapshot()
        except VeoliaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except VeoliaBlockedError as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_WAF_BLOCKED,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_WAF_BLOCKED,
            )
            raise UpdateFailed(str(err)) from err
        except VeoliaError as err:
            raise UpdateFailed(str(err)) from err

        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_WAF_BLOCKED)
        self.raw = snapshot
        locations = build_locations(snapshot)
        if self.selected_locations:
            locations = {k: v for k, v in locations.items() if k in self.selected_locations}
        if "recorder" in self.hass.config.components:
            await async_import_statistics(self.hass, locations)
        return locations
