"""Teste pentru diagnostics și issue-ul de blocare WAF."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.veolia_vrsi.api import VeoliaBlockedError
from custom_components.veolia_vrsi.diagnostics import async_get_config_entry_diagnostics

from .test_setup import setup_entry


async def test_diagnostics_redacts(hass: HomeAssistant, mock_bridge) -> None:
    entry = await setup_entry(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(diag, default=str)
    for secret in ("user@example.com", '"x"', '"tok"', "STR. EXEMPLU", "ION POPESCU", "VRS000000003", "900000000002"):
        assert secret not in text, secret
    assert diag["snapshot"]["client_codes"] == ["10000001", "10000002"]
    assert diag["entry"]["options"]["locations"] == ["4000000001"]
    assert diag["locations"]["4000000001"]["perioade"] == 3


async def test_waf_issue_created_and_cleared(hass: HomeAssistant, mock_bridge) -> None:
    entry = await setup_entry(hass)
    registry = ir.async_get(hass)
    assert registry.async_get_issue("veolia_vrsi", "waf_blocked") is None

    mock_bridge.get_snapshot.side_effect = VeoliaBlockedError("blocat")
    await entry.runtime_data.async_refresh()
    issue = registry.async_get_issue("veolia_vrsi", "waf_blocked")
    assert issue is not None
    assert issue.translation_key == "waf_blocked"

    mock_bridge.get_snapshot.side_effect = None
    await entry.runtime_data.async_refresh()
    assert registry.async_get_issue("veolia_vrsi", "waf_blocked") is None
