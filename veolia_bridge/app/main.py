"""Punctul de intrare al add-on-ului Veolia Bridge."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import aiohttp
from aiohttp import web

from .browser import PlaywrightPortal
from .invoices import InvoiceCache
from .server import create_app
from .supervisor import announce, load_or_create_token, manual_setup_hint

VERSION = "0.2.0"
PORT = 8099
DATA = Path(os.environ.get("VEOLIA_DATA_DIR", "/data"))

_LOGGER = logging.getLogger("veolia_bridge")


def _log_level() -> int:
    try:
        options = json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        options = {}
    return getattr(logging, str(options.get("log_level", "info")).upper(), logging.INFO)


def main() -> None:
    logging.basicConfig(
        level=_log_level(), format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    token = load_or_create_token(DATA / "token")
    portal = PlaywrightPortal(invoice_cache=InvoiceCache(DATA / "invoices.json"))
    app = create_app(portal, token, VERSION)

    async def on_startup(_: web.Application) -> None:
        _LOGGER.info("Veolia Bridge %s - Listening on 0.0.0.0:%s", VERSION, PORT)
        async with aiohttp.ClientSession() as session:
            if not await announce(session, token, PORT):
                _LOGGER.warning(manual_setup_hint(token, PORT))

    app.on_startup.append(on_startup)
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
