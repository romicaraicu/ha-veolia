"""Teste pentru acțiunea veolia_vrsi.trimite_index."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.veolia_vrsi.api import VeoliaConnectionError, VeoliaNotAllowedError

from .conftest import METER
from .test_setup import setup_entry


def _reading(mock_bridge) -> dict:
    return mock_bridge.snapshot_data["accounts"]["10000001"]["meters"][METER]["last_index"]


async def _call(hass: HomeAssistant, meter: str = METER, index: int = 1234):
    return await hass.services.async_call(
        "veolia_vrsi", "trimite_index", {"contor": meter, "index": index},
        blocking=True, return_response=True,
    )


async def test_rejects_smart_meter(hass: HomeAssistant, mock_bridge) -> None:
    await setup_entry(hass)
    with pytest.raises(ServiceValidationError, match="distanță"):
        await _call(hass)
    mock_bridge.submit_index.assert_not_awaited()


async def test_submits_when_open(hass: HomeAssistant, mock_bridge) -> None:
    _reading(mock_bridge)["IsSmart"] = False
    await setup_entry(hass)
    calls = mock_bridge.get_snapshot.await_count
    response = await _call(hass, meter=METER.lower())
    mock_bridge.submit_index.assert_awaited_once_with("10000001", METER, 1234)
    assert response == {"contor": METER, "index": 1234, "mesaj": "Indexul a fost salvat cu succes!"}
    await hass.async_block_till_done()
    assert mock_bridge.get_snapshot.await_count > calls


async def test_unknown_meter(hass: HomeAssistant, mock_bridge) -> None:
    await setup_entry(hass)
    with pytest.raises(ServiceValidationError, match="XX"):
        await _call(hass, meter="XX")


async def test_rejects_outside_period(hass: HomeAssistant, mock_bridge) -> None:
    _reading(mock_bridge)["IsSmart"] = False
    _reading(mock_bridge)["Inperioada"] = ""
    await setup_entry(hass)
    with pytest.raises(ServiceValidationError, match="21–25 nov. 2026"):
        await _call(hass)
    mock_bridge.submit_index.assert_not_awaited()


async def test_bridge_not_allowed(hass: HomeAssistant, mock_bridge) -> None:
    _reading(mock_bridge)["IsSmart"] = False
    await setup_entry(hass)
    mock_bridge.submit_index.side_effect = VeoliaNotAllowedError("Portalul a refuzat")
    with pytest.raises(ServiceValidationError, match="Portalul a refuzat"):
        await _call(hass)


async def test_bridge_error(hass: HomeAssistant, mock_bridge) -> None:
    _reading(mock_bridge)["IsSmart"] = False
    await setup_entry(hass)
    mock_bridge.submit_index.side_effect = VeoliaConnectionError("jos")
    with pytest.raises(HomeAssistantError, match="jos"):
        await _call(hass)


async def test_rejects_seven_digits(hass: HomeAssistant, mock_bridge) -> None:
    _reading(mock_bridge)["IsSmart"] = False
    await setup_entry(hass)
    with pytest.raises(vol.Invalid):
        await _call(hass, index=1234567)
    mock_bridge.submit_index.assert_not_awaited()
