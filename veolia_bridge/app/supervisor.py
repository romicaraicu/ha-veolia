"""Token-ul bridge-ului și anunțarea lui către Home Assistant prin Supervisor."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import secrets

import aiohttp

_LOGGER = logging.getLogger(__name__)

SUPERVISOR_URL = "http://supervisor"
SERVICE = "veolia_vrsi"


def load_or_create_token(path: Path) -> str:
    """Citește token-ul din /data sau generează unul nou (permisiuni 0600)."""
    if path.exists():
        token = path.read_text().strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(token)
    os.chmod(path, 0o600)
    return token


async def announce(
    session: aiohttp.ClientSession,
    token: str,
    port: int,
    base_url: str = SUPERVISOR_URL,
) -> bool:
    """Trimite descoperirea către integrare. Erorile sunt doar logate."""
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        _LOGGER.info("Nu rulez sub Supervisor; sar peste descoperire")
        return False
    headers = {"Authorization": f"Bearer {supervisor_token}"}
    try:
        async with session.get(f"{base_url}/addons/self/info", headers=headers) as resp:
            resp.raise_for_status()
            hostname = (await resp.json())["data"]["hostname"]
        payload = {
            "service": SERVICE,
            "config": {"host": hostname, "port": port, "token": token},
        }
        async with session.post(f"{base_url}/discovery", json=payload, headers=headers) as resp:
            resp.raise_for_status()
    except (aiohttp.ClientError, KeyError, TypeError, ValueError) as err:
        _LOGGER.error("Descoperirea prin Supervisor a eșuat: %s", err)
        return False
    _LOGGER.info("Discovery sent (%s:%s)", hostname, port)
    return True
