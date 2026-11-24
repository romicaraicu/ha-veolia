"""Teste pentru orchestrarea snapshot-ului din bridge (fără browser)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from veolia_bridge.app.errors import PortalError
from veolia_bridge.app.snapshot import build_save_index_body, build_snapshot

TODAY = date(2026, 11, 24)

ALLOWED = {
    "get-client-codes",
    "get-consumption-locations",
    "get-contracts",
    "get-last-index",
    "get-index-history",
    "get-last-invoice-and-total-payments",
    "get-unpaid-invoices",
    "get-invoices",
    "get-payments",
}

READING = {
    "Adatsoll": "2026-11-25",
    "AdatsollMin": "2026-11-21",
    "Anlage": "5000000001",
    "Equnr": "000000000010000001",
    "Inperioada": "X",
    "IsSmart": False,
    "LastIndex": 419,
    "LastIndexDate": "2026-10-28",
    "Matnr": "000000000000100001",
    "Sernr": "22AA000001",
    "Zwnummer": "001",
}


class FakePortal:
    def __init__(self, contract_start: str | None = "2023-02-27") -> None:
        self.calls: list[tuple[str, dict | None]] = []
        self.contract_start = contract_start

    async def __call__(self, endpoint: str, body: dict | None) -> Any:
        self.calls.append((endpoint, body))
        match endpoint:
            case "get-client-codes":
                return ["10000001"]
            case "get-consumption-locations":
                return {
                    "ClientNumber": "10000001",
                    "ConsumptionPointInfo": [{
                        "ConsumptionClientAddress": "STR. EXEMPLU 1",
                        "ConsumptionInstallation": "5000000001",
                        "ConsumptionMeters": ["22AA000001"],
                        "ConsumptionPointCode": "4000000001",
                    }],
                }
            case "get-contracts":
                info = []
                if self.contract_start:
                    info = [{"ConsumptionPointCode": "4000000001",
                             "ContractStartDate": self.contract_start}]
                return {"ClientNumber": "10000001", "ContractInfo": info}
            case "get-last-index":
                return {"MeterReadingDetails": dict(READING)}
            case "get-index-history":
                return {"IndexHistory": [{"Consumption": 14, "EndDate": "2026-10-28"}],
                        "GraphicDataset": {"Dates": [], "Values": []}}
            case "get-last-invoice-and-total-payments":
                return {"LastInvoiceDetails": {"InvoiceNumber": "X1"}, "TotalPaymentsSum": 258.54}
            case "get-unpaid-invoices":
                return {"UnpaidInvoices": [{"InvoiceNumber": "X1"}]}
            case "get-invoices":
                return {"PaidInvoices": [{"InvoiceNumber": f"P{body['year']}"}]}
            case "get-payments":
                return {"ClientNumber": "10000001", "Payments": [{"PaidAmount": "1"}]}
        raise AssertionError(f"endpoint neașteptat {endpoint}")


async def test_snapshot_shape() -> None:
    portal = FakePortal()
    snap = await build_snapshot(portal, TODAY)
    assert snap["client_codes"] == ["10000001"]
    assert "fetched_at" in snap
    acc = snap["accounts"]["10000001"]
    assert acc["locations"][0]["ConsumptionPointCode"] == "4000000001"
    assert acc["contracts"][0]["ContractStartDate"] == "2023-02-27"
    meter = acc["meters"]["22AA000001"]
    assert meter["consumption_point"] == "4000000001"
    assert meter["installation"] == "5000000001"
    assert meter["last_index"]["LastIndex"] == 419
    assert meter["index_history"][0]["Consumption"] == 14
    assert acc["total_to_pay"] == 258.54
    assert acc["last_invoice"]["InvoiceNumber"] == "X1"
    assert acc["unpaid_invoices"] == [{"InvoiceNumber": "X1"}]
    assert [i["InvoiceNumber"] for i in acc["paid_invoices"]] == ["P2026", "P2025", "P2024", "P2023"]
    assert acc["payments"] == [{"PaidAmount": "1"}]


async def test_index_history_uses_installation() -> None:
    portal = FakePortal()
    await build_snapshot(portal, TODAY)
    body = next(b for e, b in portal.calls if e == "get-index-history")
    assert body == {
        "clientCode": "10000001",
        "meterSernr": "22AA000001",
        "consumptionPointCode": "5000000001",
    }


async def test_invoice_years_from_contract_start() -> None:
    portal = FakePortal()
    await build_snapshot(portal, TODAY)
    years = [b["year"] for e, b in portal.calls if e == "get-invoices"]
    assert sorted(years) == ["2023", "2024", "2025", "2026"]


async def test_invoice_years_without_contract() -> None:
    portal = FakePortal(contract_start=None)
    await build_snapshot(portal, TODAY)
    years = [b["year"] for e, b in portal.calls if e == "get-invoices"]
    assert sorted(years) == ["2025", "2026"]


async def test_only_allowed_endpoints() -> None:
    portal = FakePortal()
    await build_snapshot(portal, TODAY)
    assert {e for e, _ in portal.calls} <= ALLOWED


def test_save_index_body_ok() -> None:
    assert build_save_index_body("10000001", READING, 1234) == {
        "clientCode": "10000001",
        "adatsoll": "2026-11-25",
        "anlage": "5000000001",
        "zwnummer": "001",
        "index": "1234",
        "matnr": "000000000000100001",
        "sernr": "22AA000001",
        "equnr": "000000000010000001",
    }


@pytest.mark.parametrize(
    ("changes", "index"),
    [
        ({"IsSmart": True}, 1234),
        ({"Inperioada": ""}, 1234),
        ({}, 1234567),
        ({}, -1),
    ],
    ids=["smart", "outside_period", "7_digits", "negative"],
)
def test_save_index_rejected(changes: dict, index: int) -> None:
    with pytest.raises(PortalError) as err:
        build_save_index_body("10000001", {**READING, **changes}, index)
    assert err.value.code == "not_allowed"
