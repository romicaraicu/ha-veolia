"""Testele bridge-ului pornesc servere aiohttp locale: au nevoie de socket-uri."""

import pytest


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled):
    yield
