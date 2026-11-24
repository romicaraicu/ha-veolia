"""Orchestrarea cererilor către portal, independentă de browser.

`call(endpoint, body)` returnează câmpul `content` al răspunsului portalului
sau ridică PortalError. Forma snapshot-ului: spec 5.3.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone
import re
from typing import Any

from .errors import PortalError

Call = Callable[[str, dict | None], Awaitable[Any]]

_DIGITS = re.compile(r"^\d{1,6}$")


def _list(content: Any, key: str) -> list:
    if isinstance(content, dict):
        value = content.get(key)
        return value if isinstance(value, list) else []
    return []


def _start_year(contracts: list[dict], today: date) -> int:
    years = []
    for c in contracts:
        value = str(c.get("ContractStartDate") or "")
        if re.match(r"^\d{4}-", value) and not value.startswith("0000"):
            years.append(int(value[:4]))
    return min(years) if years else today.year - 1


async def build_snapshot(call: Call, today: date) -> dict:
    """Citește tot contul și îl grupează pe coduri client."""
    client_codes = [str(c) for c in (await call("get-client-codes", None) or [])]
    accounts: dict[str, Any] = {}
    for code in client_codes:
        body = {"clientCode": code}
        locations = _list(await call("get-consumption-locations", body), "ConsumptionPointInfo")
        contracts = _list(await call("get-contracts", body), "ContractInfo")

        meters: dict[str, Any] = {}
        for loc in locations:
            installation = str(loc.get("ConsumptionInstallation") or "")
            for meter in loc.get("ConsumptionMeters") or []:
                last = await call("get-last-index", {"clientCode": code, "meterSernr": meter})
                history = await call(
                    "get-index-history",
                    {
                        "clientCode": code,
                        "meterSernr": meter,
                        # portalul trimite instalația în acest câmp
                        "consumptionPointCode": installation,
                    },
                )
                meters[str(meter)] = {
                    "consumption_point": str(loc.get("ConsumptionPointCode") or ""),
                    "installation": installation,
                    "last_index": (last or {}).get("MeterReadingDetails"),
                    "index_history": _list(history, "IndexHistory"),
                }

        summary = await call("get-last-invoice-and-total-payments", body) or {}
        unpaid = _list(await call("get-unpaid-invoices", body), "UnpaidInvoices")
        payments = _list(await call("get-payments", body), "Payments")
        paid: list[dict] = []
        for year in range(today.year, _start_year(contracts, today) - 1, -1):
            content = await call("get-invoices", {"clientCode": code, "year": str(year)})
            paid.extend(_list(content, "PaidInvoices"))

        accounts[code] = {
            "locations": locations,
            "contracts": contracts,
            "meters": meters,
            "last_invoice": summary.get("LastInvoiceDetails"),
            "total_to_pay": summary.get("TotalPaymentsSum"),
            "unpaid_invoices": unpaid,
            "paid_invoices": paid,
            "payments": payments,
        }

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "client_codes": client_codes,
        "accounts": accounts,
    }


def build_save_index_body(client_code: str, details: dict, index: int) -> dict:
    """Body-ul pentru `save-index`, cu aceleași reguli ca portalul."""
    if details.get("IsSmart") is True:
        raise PortalError(
            "not_allowed",
            "Contorul este citit de la distanță; portalul nu permite transmiterea indexului.",
        )
    if details.get("Inperioada") != "X":
        raise PortalError(
            "not_allowed",
            "Indexul poate fi transmis numai în perioada de transmitere autocitiri.",
        )
    if not isinstance(index, int) or index < 0 or not _DIGITS.match(str(index)):
        raise PortalError("not_allowed", "Indexul trebuie să aibă între 1 și 6 cifre.")
    return {
        "clientCode": str(client_code),
        "adatsoll": details.get("Adatsoll"),
        "anlage": details.get("Anlage"),
        "zwnummer": details.get("Zwnummer"),
        "index": str(index),
        "matnr": details.get("Matnr"),
        "sernr": details.get("Sernr"),
        "equnr": details.get("Equnr"),
    }
