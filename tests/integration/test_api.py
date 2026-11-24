"""Teste pentru clientul către bridge."""

from __future__ import annotations

import aiohttp
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.veolia_vrsi.api import (
    VeoliaAuthError,
    VeoliaBlockedError,
    VeoliaBridgeAuthError,
    VeoliaBridgeClient,
    VeoliaConnectionError,
    VeoliaNotAllowedError,
)

URL = "http://bridge:8099"


def _client(hass: HomeAssistant) -> VeoliaBridgeClient:
    return VeoliaBridgeClient(async_get_clientsession(hass), URL, "tok", "a@b.ro", "pw")


async def test_snapshot_ok(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(f"{URL}/snapshot", json={"client_codes": ["1"], "accounts": {}})
    assert (await _client(hass).get_snapshot())["client_codes"] == ["1"]
    _, _, body, headers = aioclient_mock.mock_calls[0]
    assert body == {"email": "a@b.ro", "password": "pw"}
    assert headers["Authorization"] == "Bearer tok"


async def test_submit_index_ok(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(f"{URL}/submit-index", json={"mesaj": "ok"})
    assert await _client(hass).submit_index("10000001", "22AA000001", 1234) == {"mesaj": "ok"}
    _, _, body, _ = aioclient_mock.mock_calls[0]
    assert body == {
        "email": "a@b.ro", "password": "pw",
        "clientCode": "10000001", "meter": "22AA000001", "index": 1234,
    }


async def test_health(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/health", json={"status": "ok"})
    assert (await _client(hass).health())["status"] == "ok"


@pytest.mark.parametrize(
    ("status", "code", "exc"),
    [
        (403, "auth", VeoliaAuthError),
        (503, "waf_blocked", VeoliaBlockedError),
        (400, "not_allowed", VeoliaNotAllowedError),
        (401, "unauthorized", VeoliaBridgeAuthError),
        (502, "portal", VeoliaConnectionError),
        (504, "timeout", VeoliaConnectionError),
    ],
)
async def test_maps_errors(hass: HomeAssistant, aioclient_mock, status, code, exc) -> None:
    aioclient_mock.post(
        f"{URL}/snapshot", status=status, json={"error": {"code": code, "message": "m"}}
    )
    with pytest.raises(exc, match="m"):
        await _client(hass).get_snapshot()


async def test_connection_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(f"{URL}/snapshot", exc=aiohttp.ClientError("down"))
    with pytest.raises(VeoliaConnectionError):
        await _client(hass).get_snapshot()


async def test_invalid_response(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(f"{URL}/snapshot", text="nu e json")
    with pytest.raises(VeoliaConnectionError):
        await _client(hass).get_snapshot()
