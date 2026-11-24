"""Descărcarea facturilor PDF și păstrarea cifrelor extrase din ele.

Fiecare factură e descărcată o singură dată: rezultatul interpretării se
păstrează în /data/invoices.json, după numărul facturii. PDF-ul nu se salvează.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
import json
import logging
import os
from pathlib import Path
from typing import Any

from .errors import PortalError
from .invoice_pdf import parse_invoice_text
from .snapshot import Call

_LOGGER = logging.getLogger(__name__)

DEFAULT_LIMIT = 6


class InvoiceCache:
    """Dicționar număr factură → detalii, salvat ca JSON."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.data: dict[str, dict] = {}
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded, dict):
                self.data = loaded
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as err:
            _LOGGER.warning("Ignor cache-ul de facturi invalid (%s)", err)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, sort_keys=True))
        os.replace(tmp, self._path)


def _account_invoices(account: dict) -> list[tuple[str, str]]:
    """(dată emitere, număr) pentru toate facturile contului, fără dubluri."""
    seen: dict[str, str] = {}
    candidates = [account.get("last_invoice")]
    candidates += account.get("unpaid_invoices") or []
    candidates += account.get("paid_invoices") or []
    for invoice in candidates:
        if not isinstance(invoice, dict):
            continue
        number = str(invoice.get("InvoiceNumber") or "")
        if number:
            seen.setdefault(number, str(invoice.get("DateIn") or ""))
    return [(date, number) for number, date in seen.items()]


def _parse(number: str, content: Any, pdf_text: Callable[[bytes], str]) -> dict:
    try:
        encoded = (content or {}).get("InvoiceContent")
        if not encoded:
            raise ValueError("răspunsul nu conține PDF")
        details = parse_invoice_text(pdf_text(base64.b64decode(encoded)))
    except Exception as err:  # noqa: BLE001 - orice PDF stricat se marchează, nu oprește snapshot-ul
        _LOGGER.warning("Factura %s nu a putut fi interpretată: %s", number, err)
        return {"invoice_number": number, "parse_error": str(err)}
    details["invoice_number"] = details.get("invoice_number") or number
    return details


async def add_invoice_details(
    call: Call,
    snapshot: dict,
    cache: InvoiceCache,
    pdf_text: Callable[[bytes], str],
    limit: int = DEFAULT_LIMIT,
) -> None:
    """Completează `invoice_details` în fiecare cont, descărcând cel mult `limit` facturi noi."""
    accounts: dict[str, dict] = snapshot.get("accounts") or {}
    pending: list[tuple[str, str, str]] = []
    for client_code, account in accounts.items():
        for issued, number in _account_invoices(account):
            if number not in cache.data:
                pending.append((issued, number, client_code))
    pending.sort(reverse=True)

    changed = False
    for _, number, client_code in pending[:limit]:
        try:
            content = await call(
                "download-invoice", {"clientCode": client_code, "invoiceNumber": number}
            )
        except PortalError as err:
            _LOGGER.warning("Factura %s nu a putut fi descărcată: %s", number, err.message)
            if err.code in ("auth", "waf_blocked", "timeout"):
                break
            continue
        cache.data[number] = await asyncio.to_thread(_parse, number, content, pdf_text)
        changed = True
    if changed:
        cache.save()

    for account in accounts.values():
        account["invoice_details"] = {
            number: cache.data[number]
            for _, number in _account_invoices(account)
            if number in cache.data
        }
