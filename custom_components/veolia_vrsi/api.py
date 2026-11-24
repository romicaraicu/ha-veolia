"""Client către add-on-ul Veolia Bridge.

Modulul nu depinde de Home Assistant (doar de aiohttp).
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=180)


class VeoliaError(Exception):
    """Eroare generică Veolia."""


class VeoliaAuthError(VeoliaError):
    """Email sau parolă greșite."""


class VeoliaBlockedError(VeoliaError):
    """Portalul a blocat browserul automat (AWS WAF / CAPTCHA)."""


class VeoliaNotAllowedError(VeoliaError):
    """Portalul nu permite operația (ex. index în afara perioadei)."""


class VeoliaBridgeAuthError(VeoliaError):
    """Token-ul bridge-ului e greșit."""


class VeoliaConnectionError(VeoliaError):
    """Bridge-ul sau portalul nu au răspuns corect."""


_ERRORS: dict[str, type[VeoliaError]] = {
    "auth": VeoliaAuthError,
    "waf_blocked": VeoliaBlockedError,
    "not_allowed": VeoliaNotAllowedError,
    "bad_request": VeoliaNotAllowedError,
    "unauthorized": VeoliaBridgeAuthError,
}


class VeoliaBridgeClient:
    """Apelează endpoint-urile add-on-ului."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        token: str,
        email: str,
        password: str,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._token = token
        self._email = email
        self._password = password

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health", None)

    async def get_snapshot(self) -> dict[str, Any]:
        return await self._request(
            "POST", "/snapshot", {"email": self._email, "password": self._password}
        )

    async def submit_index(self, client_code: str, meter: str, index: int) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/submit-index",
            {
                "email": self._email,
                "password": self._password,
                "clientCode": client_code,
                "meter": meter,
                "index": index,
            },
        )

    async def _request(self, method: str, path: str, body: dict | None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with self._session.request(
                method, f"{self._url}{path}", json=body, headers=headers, timeout=_TIMEOUT
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except ValueError:
                    raise VeoliaConnectionError(
                        f"Răspuns invalid de la bridge (HTTP {resp.status})"
                    ) from None
                status = resp.status
        except TimeoutError as err:
            raise VeoliaConnectionError("Bridge-ul nu a răspuns la timp") from err
        except aiohttp.ClientError as err:
            raise VeoliaConnectionError(f"Nu mă pot conecta la bridge: {err}") from err

        if not isinstance(data, dict):
            raise VeoliaConnectionError("Răspuns invalid de la bridge")
        if status >= 400 or "error" in data:
            error = data.get("error") or {}
            code = str(error.get("code") or "")
            message = str(error.get("message") or f"HTTP {status}")
            raise _ERRORS.get(code, VeoliaConnectionError)(message)
        return data
