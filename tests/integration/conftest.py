"""Fixtures pentru testele integrării Veolia VRSI."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


FIXTURE = Path(__file__).parent.parent / "fixtures" / "snapshot.json"
CODE = "4000000001"
METER = "22AA000001"
EMAIL = "user@example.com"
BRIDGE_URL = "http://abc-veolia-bridge:8099"


def load_snapshot() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def snapshot() -> dict:
    return copy.deepcopy(load_snapshot())


@pytest.fixture
def mock_bridge(snapshot):
    with patch(
        "custom_components.veolia_vrsi.VeoliaBridgeClient", autospec=True
    ) as client_cls, patch(
        "custom_components.veolia_vrsi.config_flow.VeoliaBridgeClient", new=client_cls
    ):
        client = client_cls.return_value
        client.health = AsyncMock(return_value={"status": "ok", "version": "0.1.0", "busy": False})
        client.get_snapshot = AsyncMock(return_value=snapshot)
        client.submit_index = AsyncMock(return_value={"mesaj": "Indexul a fost salvat cu succes!"})
        client.snapshot_data = snapshot
        yield client
