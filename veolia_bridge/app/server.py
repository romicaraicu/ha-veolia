"""Serverul HTTP intern al add-on-ului (doar rețeaua Supervisor)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from typing import Any, Protocol

from aiohttp import web

from .errors import PortalError

_LOGGER = logging.getLogger(__name__)

_STATUS = {
    "auth": 403,
    "not_allowed": 400,
    "bad_request": 400,
    "waf_blocked": 503,
    "timeout": 504,
    "portal": 502,
}

LOCK_KEY = web.AppKey("lock", asyncio.Lock)
PORTAL_KEY = web.AppKey("portal", object)


class Portal(Protocol):
    async def snapshot(self, email: str, password: str) -> dict: ...

    async def submit_index(
        self, email: str, password: str, client_code: str, meter: str, index: int
    ) -> dict: ...


def _error(code: str, message: str, status: int | None = None) -> web.Response:
    return web.json_response(
        {"error": {"code": code, "message": message}},
        status=status or _STATUS.get(code, 500),
    )


async def _read_body(request: web.Request, extra: dict[str, type]) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        raise PortalError("bad_request", "Corpul cererii nu este JSON valid.") from None
    if not isinstance(body, dict):
        raise PortalError("bad_request", "Corpul cererii trebuie să fie un obiect JSON.")
    fields = {"email": str, "password": str, **extra}
    for name, kind in fields.items():
        value = body.get(name)
        if not isinstance(value, kind) or isinstance(value, bool) or value == "":
            raise PortalError("bad_request", f"Câmpul „{name}” lipsește sau e invalid.")
    return body


def create_app(
    portal: Portal, token: str, version: str, op_timeout: float = 150.0
) -> web.Application:
    lock = asyncio.Lock()

    @web.middleware
    async def auth_middleware(request: web.Request, handler):
        if request.method == "POST":
            header = request.headers.get("Authorization", "")
            expected = f"Bearer {token}"
            if not hmac.compare_digest(header.encode(), expected.encode()):
                return _error("unauthorized", "Token bridge invalid.", 401)
        return await handler(request)

    inflight: dict[str, asyncio.Future] = {}

    async def guarded(operation) -> Any:
        # așteptarea la lacăt intră în același buget de timp ca operația,
        # ca răspunsul să vină mereu înainte de timeout-ul clientului (180 s)
        async with asyncio.timeout(op_timeout), lock:
            return await operation()

    async def run(name: str, operation, key: str | None = None) -> web.Response:
        started = time.monotonic()
        task = inflight.get(key) if key else None
        if task is None:
            task = asyncio.ensure_future(guarded(operation))
            if key:
                inflight[key] = task
                task.add_done_callback(lambda _: inflight.pop(key, None))
        else:
            _LOGGER.debug("%s: folosesc rezultatul cererii aflate deja în lucru", name)
        try:
            # shield: dacă un client renunță, cererea comună continuă pentru ceilalți
            result = await asyncio.shield(task)
        except TimeoutError:
            _LOGGER.warning("%s: depășit timpul de %.0f s", name, op_timeout)
            return _error("timeout", f"Operația a durat mai mult de {op_timeout:.0f} s.")
        except PortalError as err:
            _LOGGER.warning("%s: eroare %s (%.1f s)", name, err.code, time.monotonic() - started)
            return _error(err.code, err.message)
        _LOGGER.info("%s: gata în %.1f s", name, time.monotonic() - started)
        return web.json_response(result)

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "version": version, "busy": lock.locked()})

    async def snapshot(request: web.Request) -> web.Response:
        try:
            body = await _read_body(request, {})
        except PortalError as err:
            return _error(err.code, err.message)
        key = hashlib.sha256(f"{body['email']}\0{body['password']}".encode()).hexdigest()
        return await run(
            "snapshot", lambda: portal.snapshot(body["email"], body["password"]), key
        )

    async def submit_index(request: web.Request) -> web.Response:
        try:
            body = await _read_body(request, {"clientCode": str, "meter": str, "index": int})
        except PortalError as err:
            return _error(err.code, err.message)
        return await run(
            "submit-index",
            lambda: portal.submit_index(
                body["email"], body["password"], body["clientCode"], body["meter"], body["index"]
            ),
        )

    app = web.Application(middlewares=[auth_middleware])
    app.router.add_get("/health", health)
    app.router.add_post("/snapshot", snapshot)
    app.router.add_post("/submit-index", submit_index)
    return app
