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


_CREDENTIAL_WORDS = ("parol", "incorect", "email", "e-mail", "utilizator", "contul", "autentific")


def _plain(text: str) -> str:
    table = str.maketrans("ăâîșşțţ", "aaisstt")
    return text.lower().translate(table)


def classify_login_failure(data: dict) -> PortalError:
    """`login-submit` a eșuat: credențiale greșite (`auth`) sau problemă a portalului."""
    code = data.get("code")
    message = str(data.get("error") or "")
    plain = _plain(message)
    if isinstance(code, int) and code >= 500:
        return PortalError("portal", message or f"Portalul a răspuns cu codul {code}.")
    if any(word in plain for word in _CREDENTIAL_WORDS) or code in (401, 403) or not message:
        return PortalError("auth", message or "Autentificare eșuată.")
    return PortalError("portal", message)


def classify_call_failure(endpoint: str, data: dict) -> PortalError:
    """Un apel de date a eșuat după login: niciodată `auth` (parola a fost acceptată)."""
    message = data.get("error") or "eroare portal"
    if data.get("code") == 401:
        message = f"sesiunea a expirat ({message})"
    return PortalError("portal", f"{endpoint}: {message}")
