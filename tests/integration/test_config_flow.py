"""Teste pentru config flow."""

from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.veolia_vrsi.api import (
    VeoliaAuthError,
    VeoliaBlockedError,
    VeoliaBridgeAuthError,
    VeoliaConnectionError,
)
from custom_components.veolia_vrsi.const import (
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_LOCATIONS,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

from .conftest import BRIDGE_URL, CODE, EMAIL

CREDS = {CONF_EMAIL: EMAIL, CONF_PASSWORD: "x"}
BRIDGE = {CONF_BRIDGE_URL: BRIDGE_URL, CONF_BRIDGE_TOKEN: "tok"}
DISCOVERY = HassioServiceInfo(
    config={"host": "abc-veolia-bridge", "port": 8099, "token": "tok"},
    name="Veolia Bridge",
    slug="abc_veolia_bridge",
    uuid="1234",
)


async def _start_user(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], BRIDGE)
    assert result["step_id"] == "credentials"
    return result


async def test_user_flow_creates_entry(hass: HomeAssistant, mock_bridge) -> None:
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    # snapshot-ul are două locuri -> pasul de selecție
    assert result["step_id"] == "locations"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATIONS: [CODE], CONF_SCAN_INTERVAL: 6}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY, result
    assert result["title"] == EMAIL
    assert result["data"] == {**CREDS, **BRIDGE}
    assert result["options"] == {CONF_LOCATIONS: [CODE], CONF_SCAN_INTERVAL: 6}
    assert result["result"].unique_id == EMAIL


async def test_single_location_skips_selection(hass: HomeAssistant, mock_bridge) -> None:
    del mock_bridge.snapshot_data["accounts"]["10000002"]
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_LOCATIONS] == [CODE]


async def test_hassio_discovery_flow(hass: HomeAssistant, mock_bridge) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=DISCOVERY
    )
    assert result["step_id"] == "hassio_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "credentials"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LOCATIONS: [CODE], CONF_SCAN_INTERVAL: 6}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BRIDGE_URL] == "http://abc-veolia-bridge:8099"
    assert result["data"][CONF_BRIDGE_TOKEN] == "tok"


async def test_hassio_discovery_updates_existing_entry(hass: HomeAssistant, mock_bridge) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=EMAIL,
        data={**CREDS, CONF_BRIDGE_URL: "http://old:8099", CONF_BRIDGE_TOKEN: "old"},
        options={CONF_LOCATIONS: [CODE]},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_BRIDGE_URL] == "http://abc-veolia-bridge:8099"
    assert entry.data[CONF_BRIDGE_TOKEN] == "tok"


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (VeoliaAuthError("x"), "invalid_auth"),
        (VeoliaBlockedError("x"), "waf_blocked"),
        (VeoliaBridgeAuthError("x"), "bridge_auth"),
        (VeoliaConnectionError("x"), "cannot_connect"),
    ],
)
async def test_credential_errors(hass: HomeAssistant, mock_bridge, exc, error) -> None:
    mock_bridge.get_snapshot.side_effect = exc
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["errors"] == {"base": error}


async def test_no_locations(hass: HomeAssistant, mock_bridge) -> None:
    mock_bridge.snapshot_data["accounts"] = {}
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["errors"] == {"base": "no_locations"}


async def test_duplicate_email_aborts(hass: HomeAssistant, mock_bridge) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=EMAIL, data={**CREDS, **BRIDGE}).add_to_hass(hass)
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_password(hass: HomeAssistant, mock_bridge) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=EMAIL, data={**CREDS, **BRIDGE},
        options={CONF_LOCATIONS: [CODE]},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "nou"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "nou"


async def test_options_interval(hass: HomeAssistant, mock_bridge) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=EMAIL, data={**CREDS, **BRIDGE},
        options={CONF_LOCATIONS: [CODE], CONF_SCAN_INTERVAL: 6},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_LOCATIONS: [CODE], CONF_SCAN_INTERVAL: 12}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 12
