"""Interpretarea textului din factura PDF Veolia."""

from __future__ import annotations

from pathlib import Path

import pytest

from veolia_bridge.app.invoice_pdf import parse_invoice_text, ro_number

FIXTURES = Path(__file__).parent.parent / "fixtures" / "invoices"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.mark.parametrize(
    ("raw", "value"),
    [("3.355", 3355.0), ("14,89", 14.89), ("1.020,50", 1020.5), ("0,00", 0.0), ("11", 11.0), ("x", None)],
)
def test_ro_number(raw: str, value) -> None:
    assert ro_number(raw) == value


def test_two_meters() -> None:
    inv = parse_invoice_text(_text("factura_2_contoare.txt"))
    assert inv["invoice_number"] == "VAS000000002"
    assert inv["issued"] == "2026-11-03"
    assert inv["due"] == "2026-11-18"
    assert inv["period_start"] == "2026-09-29"
    assert inv["period_end"] == "2026-10-28"
    assert inv["meters"] == [
        {"serial": "22AA000001", "kind": "individual", "index_new": 419.0, "index_old": 408.0,
         "consumption": 11.0, "method": "citire", "reason": None, "date": "2026-10-28"},
        {"serial": "I23AA000009", "kind": "condominiu", "index_new": 3355.0, "index_old": 3253.0,
         "consumption": 102.0, "method": "citire", "reason": None, "date": "2026-10-28"},
    ]
    apa = inv["services"]["apa"]
    assert (apa["quantity"], apa["tariff"], apa["value"], apa["vat_rate"], apa["vat"], apa["total"]) == (
        14.89, 7.26, 108.09, 11.0, 11.89, 119.98)
    assert inv["services"]["canalizare"]["quantity"] == 11.91
    assert inv["services"]["canalizare"]["tariff"] == 10.48
    assert inv["services"]["apa_meteorica"]["quantity"] == 0.0
    assert (inv["total_without_vat"], inv["vat"], inv["total"]) == (232.92, 25.62, 258.54)
    assert inv["next_reading"] == "2026-11-26"
    assert inv["reading_window"] == ["2026-11-21", "2026-11-25"]


def test_no_personal_data_in_result() -> None:
    inv = parse_invoice_text(_text("factura_2_contoare.txt"))
    text = repr(inv)
    for secret in ("ION POPESCU", "STR. EXEMPLU", "RO00BANK", "10000001", "VS00000001"):
        assert secret not in text


def test_one_meter() -> None:
    inv = parse_invoice_text(_text("factura_1_contor.txt"))
    assert [m["serial"] for m in inv["meters"]] == ["22AA000001"]
    assert "apa_meteorica" not in inv["services"]
    assert inv["total"] == 225.74


def test_three_meters_with_reason_and_thousands() -> None:
    inv = parse_invoice_text(_text("factura_3_contoare.txt"))
    assert [(m["serial"], m["kind"]) for m in inv["meters"]] == [
        ("22AA000001", "individual"), ("22AA000002", "individual"), ("I23AA000009", "condominiu"),
    ]
    second = inv["meters"][1]
    assert second["method"] == "estimare"
    assert second["reason"] == "contor inaccesibil"
    assert second["index_new"] == 1205.0
    assert inv["services"]["apa"]["quantity"] == 1020.5
    assert inv["total"] == 17720.82
    assert inv["next_reading"] is None
    assert inv["reading_window"] is None


def test_other_meter_kind_is_slugged() -> None:
    text = _text("factura_1_contor.txt").replace(
        "Serie contor Index nou", "Serie contor apă caldă Index nou"
    )
    inv = parse_invoice_text(text)
    assert inv["meters"][0]["kind"] == "apa_calda"


def test_text_without_details() -> None:
    inv = parse_invoice_text("FACTURĂ Nr. VAS1\nceva fără tabele")
    assert inv["invoice_number"] == "VAS1"
    assert inv["meters"] == []
    assert inv["services"] == {}
    assert inv["total"] is None
