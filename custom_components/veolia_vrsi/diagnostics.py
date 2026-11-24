"""Diagnostics pentru Veolia VRSI (fără date personale)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import VeoliaConfigEntry
from .const import CONF_BRIDGE_TOKEN

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_BRIDGE_TOKEN,
    "ClientName",
    "Address",
    "AddressConsumptionPoint",
    "ConsumptionClientAddress",
    "ConsumptionPointAddress",
    "InvoiceNumber",
    "DocumentNumber",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VeoliaConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    locations = {
        code: {
            "contoare": len(loc.meters),
            "perioade": len(loc.periods),
            "facturi_neplatite": len(loc.unpaid),
            "facturi_platite": len(loc.paid),
            "plati": len(loc.payments),
            "contor_smart": loc.is_smart,
            "perioada_index": loc.reading_label,
        }
        for code, loc in (coordinator.data or {}).items()
    }
    return {
        "entry": {
            "title": "**REDACTED**",
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "last_update_success": coordinator.last_update_success,
        "locations": locations,
        "snapshot": async_redact_data(coordinator.raw, TO_REDACT),
    }
