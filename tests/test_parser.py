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
