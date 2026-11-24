"""Clasificarea răspunsurilor de eroare ale portalului (fără browser)."""

from __future__ import annotations

import pytest

from veolia_bridge.app.errors import classify_call_failure, classify_login_failure


@pytest.mark.parametrize(
    "data",
    [
        {"success": False, "code": 401, "error": "Date de autentificare incorecte!"},
        {"success": False, "code": 400, "error": "Email sau parola incorecta"},
        {"success": False, "error": "Utilizatorul nu exista"},
        {"success": False, "code": 403, "error": None},
    ],
)
def test_login_credential_errors_are_auth(data: dict) -> None:
    assert classify_login_failure(data).code == "auth"


@pytest.mark.parametrize(
    "data",
    [
        {"success": False, "code": 500, "error": "Serviciu indisponibil, reveniti mai tarziu"},
        {"success": False, "code": 503, "error": "Mentenanta"},
        {"success": False, "error": "Eroare SAP: timeout la comunicare"},
    ],
)
def test_login_service_errors_are_portal(data: dict) -> None:
    assert classify_login_failure(data).code == "portal"


def test_mid_session_401_is_portal_not_auth() -> None:
    err = classify_call_failure("get-invoices", {"success": False, "code": 401, "error": "Neautorizat!"})
    assert err.code == "portal"


def test_call_failure_keeps_message() -> None:
    err = classify_call_failure("get-payments", {"success": False, "code": 500, "error": "boom"})
    assert err.code == "portal"
    assert "get-payments" in err.message and "boom" in err.message
