"""Descărcarea facturilor PDF cu cache."""

from __future__ import annotations

import base64
import json
from typing import Any

from veolia_bridge.app.errors import PortalError
from veolia_bridge.app.invoices import InvoiceCache, add_invoice_details


def _snapshot() -> dict:
    inv = lambda n, d: {"InvoiceNumber": n, "DateIn": d}  # noqa: E731
    return {
        "client_codes": ["1"],
        "accounts": {
            "1": {
                "last_invoice": inv("F9", "2026-11-03"),
                "unpaid_invoices": [inv("F9", "2026-11-03")],
                "paid_invoices": [inv(f"F{i}", f"2026-{i:02d}-05") for i in range(1, 9)],
            }
        },
    }


class FakePortal:
    def __init__(self, fail: set[str] | None = None) -> None:
        self.requested: list[str] = []
        self.fail = fail or set()

    async def __call__(self, endpoint: str, body: dict | None) -> Any:
        assert endpoint == "download-invoice"
        number = body["invoiceNumber"]
        assert body["clientCode"] == "1"
        self.requested.append(number)
        if number in self.fail:
            raise PortalError("portal", "download-invoice: eroare")
        return {"InvoiceContent": base64.b64encode(number.encode()).decode()}


def fake_pdf_text(data: bytes) -> str:
    number = data.decode()
    if number == "F_BAD":
        raise ValueError("PDF stricat")
    return f" FACTURĂ Nr. {number}\nPerioada de facturare: 01.01.2026 - 31.01.2026\n"


async def test_fetches_newest_first_up_to_limit(tmp_path) -> None:
    portal = FakePortal()
    cache = InvoiceCache(tmp_path / "invoices.json")
    snap = _snapshot()
    await add_invoice_details(portal, snap, cache, fake_pdf_text, limit=3)
    assert portal.requested == ["F9", "F8", "F7"]
    details = snap["accounts"]["1"]["invoice_details"]
    assert set(details) == {"F9", "F8", "F7"}
    assert details["F9"]["invoice_number"] == "F9"


async def test_cache_avoids_second_download(tmp_path) -> None:
    path = tmp_path / "invoices.json"
    snap = _snapshot()
    await add_invoice_details(FakePortal(), snap, InvoiceCache(path), fake_pdf_text, limit=3)

    portal = FakePortal()
    snap2 = _snapshot()
    await add_invoice_details(portal, snap2, InvoiceCache(path), fake_pdf_text, limit=3)
    assert portal.requested == ["F6", "F5", "F4"]
    assert set(snap2["accounts"]["1"]["invoice_details"]) == {"F9", "F8", "F7", "F6", "F5", "F4"}


async def test_portal_error_is_retried_later(tmp_path) -> None:
    cache = InvoiceCache(tmp_path / "invoices.json")
    snap = _snapshot()
    await add_invoice_details(FakePortal(fail={"F9"}), snap, cache, fake_pdf_text, limit=2)
    assert set(snap["accounts"]["1"]["invoice_details"]) == {"F8"}
    portal = FakePortal()
    await add_invoice_details(portal, _snapshot(), cache, fake_pdf_text, limit=1)
    assert portal.requested == ["F9"]


async def test_bad_pdf_is_cached_as_parse_error(tmp_path) -> None:
    snap = {"client_codes": ["1"], "accounts": {"1": {
        "last_invoice": None, "unpaid_invoices": [], "paid_invoices": [{"InvoiceNumber": "F_BAD", "DateIn": "2026-01-01"}],
    }}}
    cache = InvoiceCache(tmp_path / "invoices.json")
    await add_invoice_details(FakePortal(), snap, cache, fake_pdf_text, limit=5)
    assert "parse_error" in snap["accounts"]["1"]["invoice_details"]["F_BAD"]
    portal = FakePortal()
    await add_invoice_details(portal, snap, cache, fake_pdf_text, limit=5)
    assert portal.requested == []


async def test_cache_file_persisted_and_corrupt_file_ignored(tmp_path) -> None:
    path = tmp_path / "invoices.json"
    path.write_text("{nu e json")
    cache = InvoiceCache(path)
    await add_invoice_details(FakePortal(), _snapshot(), cache, fake_pdf_text, limit=1)
    assert "F9" in json.loads(path.read_text())


async def test_account_without_invoices(tmp_path) -> None:
    snap = {"client_codes": ["1"], "accounts": {"1": {"last_invoice": None, "unpaid_invoices": [], "paid_invoices": []}}}
    await add_invoice_details(FakePortal(), snap, InvoiceCache(tmp_path / "i.json"), fake_pdf_text, limit=6)
    assert snap["accounts"]["1"]["invoice_details"] == {}


async def test_blocked_portal_stops_fetching_but_keeps_snapshot(tmp_path) -> None:
    class Blocked(FakePortal):
        async def __call__(self, endpoint, body):
            self.requested.append(body["invoiceNumber"])
            raise PortalError("waf_blocked", "blocat")

    portal = Blocked()
    snap = _snapshot()
    await add_invoice_details(portal, snap, InvoiceCache(tmp_path / "i.json"), fake_pdf_text, limit=6)
    assert portal.requested == ["F9"]
    assert snap["accounts"]["1"]["invoice_details"] == {}
