"""Integrarea Veolia VRSI pentru Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VeoliaBridgeClient, VeoliaError, VeoliaNotAllowedError
from .const import (
    ATTR_INDEX,
    ATTR_METER,
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    DOMAIN,
    SERVICE_SUBMIT_INDEX,
)
from .coordinator import VeoliaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type VeoliaConfigEntry = ConfigEntry[VeoliaCoordinator]

SUBMIT_INDEX_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_METER): cv.string,
        vol.Required(ATTR_INDEX): vol.All(vol.Coerce(int), vol.Range(min=0, max=999999)),
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Înregistrează acțiunea de transmitere a indexului."""

    async def _submit_index(call: ServiceCall) -> ServiceResponse:
        meter = call.data[ATTR_METER].strip().upper()
        index = call.data[ATTR_INDEX]
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            coordinator: VeoliaCoordinator = entry.runtime_data
            location = next(
                (
                    loc
                    for loc in (coordinator.data or {}).values()
                    if meter in (m.upper() for m in loc.meters)
                ),
                None,
            )
            if location is None:
                continue
            if location.is_smart:
                raise ServiceValidationError(
                    "Contorul este citit de la distanță; portalul nu permite transmiterea indexului."
                )
            if not location.reading_open:
                period = location.reading_label or "necunoscută"
                raise ServiceValidationError(
                    f"Indexul poate fi transmis doar în perioada de autocitire ({period})."
                )
            try:
                result = await coordinator.api.submit_index(location.client_code, meter, index)
            except VeoliaNotAllowedError as err:
                raise ServiceValidationError(str(err)) from err
            except VeoliaError as err:
                raise HomeAssistantError(f"Indexul nu a fost transmis: {err}") from err
            await coordinator.async_request_refresh()
            message = result.get("mesaj") if isinstance(result, dict) else None
            return {"contor": meter, "index": index, "mesaj": message or "Index transmis"}
        raise ServiceValidationError(f"Contorul {meter} nu este configurat")

    hass.services.async_register(
        DOMAIN,
        SERVICE_SUBMIT_INDEX,
        _submit_index,
        schema=SUBMIT_INDEX_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VeoliaConfigEntry) -> bool:
    """Configurează o intrare (un cont Veolia)."""
    api = VeoliaBridgeClient(
        async_get_clientsession(hass),
        entry.data[CONF_BRIDGE_URL],
        entry.data[CONF_BRIDGE_TOKEN],
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = VeoliaCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: VeoliaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VeoliaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
