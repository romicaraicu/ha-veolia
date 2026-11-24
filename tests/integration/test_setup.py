"""Teste pentru setup și coordinator."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.veolia_vrsi.api import VeoliaAuthError, VeoliaConnectionError
from custom_components.veolia_vrsi.const import (
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_LOCATIONS,
    DOMAIN,
)

from .conftest import BRIDGE_URL, CODE, EMAIL


async def setup_entry(hass: HomeAssistant, locations: list[str] | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=EMAIL,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: "x", CONF_BRIDGE_URL: BRIDGE_URL, CONF_BRIDGE_TOKEN: "tok"},
        options={CONF_LOCATIONS: locations if locations is not None else [CODE]},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_filters_locations(hass: HomeAssistant, mock_bridge) -> None:
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert set(entry.runtime_data.data) == {CODE}
    assert entry.runtime_data.raw["client_codes"] == ["10000001", "10000002"]


async def test_setup_all_locations_when_none_selected(hass: HomeAssistant, mock_bridge) -> None:
    entry = await setup_entry(hass, locations=[])
    assert set(entry.runtime_data.data) == {CODE, "4000000002"}


async def test_bridge_down_is_update_failed_not_reauth(hass: HomeAssistant, mock_bridge) -> None:
    entry = await setup_entry(hass)
    mock_bridge.get_snapshot.side_effect = VeoliaConnectionError("bridge oprit")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert entry.runtime_data.last_update_success is False
    assert entry.state is ConfigEntryState.LOADED
    assert not [f for f in hass.config_entries.flow.async_progress() if f["context"]["source"] == "reauth"]


async def test_auth_failure_starts_reauth(hass: HomeAssistant, mock_bridge) -> None:
    entry = await setup_entry(hass)
    mock_bridge.get_snapshot.side_effect = VeoliaAuthError("parolă greșită")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_unload(hass: HomeAssistant, mock_bridge) -> None:
    entry = await setup_entry(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
