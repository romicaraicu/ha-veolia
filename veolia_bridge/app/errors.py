"""Erorile bridge-ului, cu coduri stabile citite de integrare."""

from __future__ import annotations

CODES = ("auth", "waf_blocked", "portal", "timeout", "not_allowed", "bad_request")


class PortalError(Exception):
    """Eroare la discuția cu portalul Veolia."""

    def __init__(self, code: str, message: str) -> None:
        if code not in CODES:
            raise ValueError(f"cod de eroare necunoscut: {code}")
        super().__init__(message)
        self.code = code
        self.message = message
