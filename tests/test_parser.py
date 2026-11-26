"""Teste pentru parser.py (fără Home Assistant)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from custom_components.veolia_vrsi.parser import build_locations, parse_date, to_float

TODAY = date(2026, 11, 24)
FIXTURE = Path(__file__).parent / "fixtures" / "snapshot.json"


@pytest.fixture
def snap() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def loc(snap):
    return build_locations(snap)["4000000001"]


@pytest.fixture
def empty(snap):
    return build_locations(snap)["4000000002"]


def test_dates_and_numbers() -> None:
    assert parse_date("0000-00-00") is None
    assert parse_date("") is None
    assert parse_date(None) is None
    assert parse_date("2026-11-18") == date(2026, 11, 18)
    assert to_float("258.54") == 258.54
    assert to_float(14) == 14.0
    assert to_float(None) is None
    assert to_float("") is None


def test_location_basic(loc) -> None:
    assert loc.client_code == "10000001"
    assert loc.code == "4000000001"
    assert loc.meter == "22AA000001"
    assert loc.address.startswith("STR. EXEMPLU")
    assert loc.last_period.consumption == 14
    assert loc.monthly_consumption()["2026-10"] == 14
    assert loc.yearly_consumption() == {"2026": 27, "2025": 9}
    assert loc.current_year_consumption(TODAY) == 27
    assert loc.last_index == 419
    assert loc.last_index_date == date(2026, 10, 28)
    assert loc.contract["ContractNumber"] == "7000000001"


def test_invoices(loc) -> None:
    assert loc.total_to_pay == 258.54
    assert loc.unpaid[0].is_overdue(TODAY) is True
    assert loc.unpaid[0].paid_on is None
    assert loc.overdue_amount(TODAY) == 258.54
    assert loc.next_due_date(TODAY) == date(2026, 11, 18)
    assert len(loc.paid_recent(TODAY)) == 2
    assert loc.paid_yearly_totals() == {"2026": 120.0, "2025": 95.1}
    assert loc.last_payment.amount == 120.0
    assert loc.last_payment.kind == "Incasare PayU"
    assert loc.last_invoice.total == 258.54


def test_reading_window(loc) -> None:
    assert loc.reading_start == date(2026, 11, 21)
    assert loc.reading_end == date(2026, 11, 25)
    assert loc.reading_label == "21–25 nov. 2026"
    assert loc.is_smart is True
    assert loc.reading_open is False
    loc.reading["IsSmart"] = False
    assert loc.reading_open is True
    loc.reading["Inperioada"] = ""
    assert loc.reading_open is False


def test_reading_label_across_months(loc) -> None:
    loc.reading["AdatsollMin"] = "2026-11-28"
    loc.reading["Adatsoll"] = "2026-12-02"
    assert loc.reading_label == "28 nov.–2 dec. 2026"


def test_multiple_accounts_and_meterless_location(snap) -> None:
    locs = build_locations(snap)
    assert set(locs) == {"4000000001", "4000000002"}
    other = locs["4000000002"]
    assert other.client_code == "10000002"
    assert other.meter is None
    assert other.last_index is None
    assert other.reading_label is None
    assert other.reading_open is False


def test_empty_account(empty) -> None:
    assert empty.periods == []
    assert empty.last_period is None
    assert empty.yearly_consumption() == {}
    assert empty.current_year_consumption(TODAY) == 0
    assert empty.total_to_pay in (None, 0)
    assert empty.next_due_date(TODAY) is None
    assert empty.overdue_amount(TODAY) == 0
    assert empty.last_payment is None
    assert empty.last_invoice is None
    assert empty.paid_recent(TODAY) == []


def test_history_merged_across_meters(snap) -> None:
    acc = snap["accounts"]["10000001"]
    acc["locations"][0]["ConsumptionMeters"] = ["22AA000001", "OLD0000001"]
    acc["meters"]["OLD0000001"] = {
        "consumption_point": "4000000001",
        "installation": "5000000001",
        "last_index": None,
        "index_history": [
            {"Consumption": 5, "EndDate": "2025-11-28", "Index": "100", "StartDate": "2025-10-29", "Type": "citire"},
            {"Consumption": 5, "EndDate": "2025-11-28", "Index": "100", "StartDate": "2025-10-29", "Type": "citire"},
        ],
    }
    loc = build_locations(snap)["4000000001"]
    assert loc.meter == "22AA000001"
    assert loc.last_index == 419
    assert [p.end.isoformat() for p in loc.periods] == [
        "2026-10-28", "2026-09-28", "2025-12-30", "2025-11-28",
    ]
    assert loc.yearly_consumption() == {"2026": 27, "2025": 14}


def test_invoice_details_and_prices(loc) -> None:
    assert [d.number for d in loc.invoice_details] == ["VRS000000003", "VRS000000002"]
    latest = loc.latest_invoice_detail
    assert latest.period_end == date(2026, 10, 28)
    assert latest.month == "2026-10"
    assert latest.water_billed == 14.89
    assert latest.tariff("apa") == 7.26
    assert latest.tariff("canalizare") == 10.48
    assert latest.tariff("necunoscut") is None
    assert latest.price_per_m3 == 17.36
    assert latest.own_consumption == 11.0
    assert latest.effective_cost_per_m3 == 23.5
    assert latest.billed_difference == 3.89


def test_meter_readings_are_dynamic(loc) -> None:
    readings = loc.meter_readings()
    assert list(readings) == ["22AA000001", "I23AA000009"]
    condo = readings["I23AA000009"]
    assert (condo.kind, condo.consumption, condo.index_new, condo.date) == (
        "condominiu", 102.0, 3355.0, date(2026, 10, 28))
    assert loc.meter_monthly("I23AA000009") == {"2026-09": 100.0, "2026-10": 102.0}
    assert loc.billed_monthly() == {"2026-09": 13.0, "2026-10": 14.89}
    assert loc.price_monthly() == {"2026-09": 17.36, "2026-10": 17.36}
    assert loc.cost_monthly() == {"2026-09": 225.74, "2026-10": 258.54}


def test_invoice_assigned_by_meter_when_account_has_several_locations(snap) -> None:
    acc = snap["accounts"]["10000001"]
    acc["locations"].append({
        "ConsumptionClientAddress": "STR. ALTA 3", "ConsumptionInstallation": "5000000003",
        "ConsumptionMeters": ["22ZZ000003"], "ConsumptionPointCode": "4000000003",
    })
    locs = build_locations(snap)
    assert len(locs["4000000001"].invoice_details) == 2
    assert locs["4000000003"].invoice_details == []
    assert locs["4000000003"].meter_readings() == {}


def test_single_location_gets_invoices_even_if_meter_not_listed(snap) -> None:
    snap["accounts"]["10000001"]["locations"][0]["ConsumptionMeters"] = ["ALT0000001"]
    loc = build_locations(snap)["4000000001"]
    assert len(loc.invoice_details) == 2


def test_location_without_invoice_details(empty) -> None:
    assert empty.latest_invoice_detail is None
    assert empty.meter_readings() == {}
    assert empty.price_monthly() == {}


def test_price_yearly_is_weighted_by_billed_water(snap) -> None:
    details = snap["accounts"]["10000001"]["invoice_details"]
    old = json.loads(json.dumps(details["VRS000000002"]))
    old.update(invoice_number="VRS000000001", period_start="2025-11-29",
               period_end="2025-12-28", total=100.0)
    old["services"]["apa"]["quantity"] = 10.0
    details["VRS000000001"] = old
    loc = build_locations(snap)["4000000001"]
    yearly = loc.price_yearly()
    assert list(yearly) == ["2026", "2025"]
    # (258,54 + 225,74) / (14,89 + 13,00): ponderat cu apa facturată
    assert yearly["2026"] == {"pret_mc": 17.36, "total": 484.28, "m3": 27.89, "facturi": 2}
    assert yearly["2025"] == {"pret_mc": 10.0, "total": 100.0, "m3": 10.0, "facturi": 1}


def test_price_yearly_empty(empty) -> None:
    assert empty.price_yearly() == {}
