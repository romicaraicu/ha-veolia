"""Teste pentru importul statisticilor lunare de consum."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from unittest.mock import patch

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import HomeAssistant

from custom_components.veolia_vrsi.parser import Period, build_locations
from custom_components.veolia_vrsi.statistics import (
    async_import_statistics,
    monthly_rows,
    statistic_id,
)

from .conftest import CODE, load_snapshot

TZ = ZoneInfo("Europe/Bucharest")


def test_statistic_id() -> None:
    assert statistic_id(CODE) == "veolia_vrsi:consum_apa_4000000001"


def test_monthly_rows() -> None:
    loc = build_locations(load_snapshot())[CODE]
    rows = monthly_rows(loc, TZ)
    assert rows == [
        (datetime(2025, 12, 1, tzinfo=TZ), 9.0, 9.0),
        (datetime(2026, 9, 1, tzinfo=TZ), 13.0, 22.0),
        (datetime(2026, 10, 1, tzinfo=TZ), 14.0, 36.0),
    ]


def test_monthly_rows_empty() -> None:
    loc = build_locations(load_snapshot())["4000000002"]
    assert monthly_rows(loc, TZ) == []


def _captured(mock_add) -> list[tuple[dict, list[tuple[str, float, float]]]]:
    result = []
    for call in mock_add.call_args_list:
        _, metadata, stats = call.args
        if not metadata["statistic_id"].startswith("veolia_vrsi:consum_apa_"):
            continue
        rows = [(s["start"].strftime("%Y-%m-%d %H:%M"), s["state"], s["sum"]) for s in stats]
        result.append((metadata, rows))
    return result


async def test_statistics_idempotent_and_merge_same_month(hass: HomeAssistant) -> None:
    await hass.config.async_set_time_zone("Europe/Bucharest")
    locations = build_locations(load_snapshot())
    loc = locations[CODE]
    loc.periods.append(
        Period(start=None, end=datetime(2026, 10, 2).date(), consumption=2, index=None, kind="citire")
    )

    with patch(
        "custom_components.veolia_vrsi.statistics.async_add_external_statistics"
    ) as mock_add:
        await async_import_statistics(hass, locations)
        await async_import_statistics(hass, locations)

    (meta1, rows1), (meta2, rows2) = _captured(mock_add)
    # locul fără istoric nu produce statistici de consum
    assert (meta1, rows1) == (meta2, rows2)
    assert rows1 == [
        ("2025-12-01 00:00", 9.0, 9.0),
        ("2026-09-01 00:00", 13.0, 22.0),
        ("2026-10-01 00:00", 16.0, 38.0),
    ]
    assert meta1["statistic_id"] == statistic_id(CODE)
    assert meta1["source"] == "veolia_vrsi"
    assert meta1["has_sum"] is True
    assert meta1["unit_of_measurement"] == "m³"
    assert meta1["unit_class"] == "volume"


def test_monthly_rows_with_base() -> None:
    loc = build_locations(load_snapshot())[CODE]
    rows = monthly_rows(loc, TZ, base=100.0)
    assert [r[2] for r in rows] == [109.0, 122.0, 136.0]


async def test_import_anchors_on_stored_sum(hass: HomeAssistant) -> None:
    """Dacă există deja statistici înainte de prima lună importată, suma continuă de la ele."""
    await hass.config.async_set_time_zone("Europe/Bucharest")
    loc = build_locations(load_snapshot())[CODE]
    with patch(
        "custom_components.veolia_vrsi.statistics._async_stored_sum_before",
        return_value=50.0,
    ) as stored, patch(
        "custom_components.veolia_vrsi.statistics.async_add_external_statistics"
    ) as mock_add:
        await async_import_statistics(hass, {CODE: loc})
    first = stored.await_args_list[0]
    assert first.args[1] == statistic_id(CODE)
    assert first.args[2] == datetime(2025, 12, 1, tzinfo=TZ)
    (_, stats), = [
        (c.args[1], c.args[2]) for c in mock_add.call_args_list
        if c.args[1]["statistic_id"] == statistic_id(CODE)
    ]
    assert [s["sum"] for s in stats] == [59.0, 72.0, 86.0]


def test_invoice_statistic_ids() -> None:
    from custom_components.veolia_vrsi.statistics import (
        billed_statistic_id,
        meter_statistic_id,
        price_statistic_id,
    )

    assert meter_statistic_id("I23AA000009") == "veolia_vrsi:contor_i23aa000009"
    assert billed_statistic_id(CODE) == "veolia_vrsi:apa_facturata_4000000001"
    assert price_statistic_id(CODE) == "veolia_vrsi:pret_mc_4000000001"


async def test_invoice_statistics_imported(hass: HomeAssistant) -> None:
    await hass.config.async_set_time_zone("Europe/Bucharest")
    locations = {CODE: build_locations(load_snapshot())[CODE]}
    with patch(
        "custom_components.veolia_vrsi.statistics.async_add_external_statistics"
    ) as mock_add:
        await async_import_statistics(hass, locations)

    by_id = {c.args[1]["statistic_id"]: (c.args[1], c.args[2]) for c in mock_add.call_args_list}
    assert set(by_id) == {
        "veolia_vrsi:consum_apa_4000000001",
        "veolia_vrsi:contor_22aa000001",
        "veolia_vrsi:contor_i23aa000009",
        "veolia_vrsi:apa_facturata_4000000001",
        "veolia_vrsi:pret_mc_4000000001",
    }
    meta, stats = by_id["veolia_vrsi:contor_i23aa000009"]
    assert meta["has_sum"] is True
    assert meta["unit_of_measurement"] == "m³"
    assert [(s["start"].strftime("%Y-%m"), s["state"], s["sum"]) for s in stats] == [
        ("2026-09", 100.0, 100.0), ("2026-10", 102.0, 202.0),
    ]
    meta, stats = by_id["veolia_vrsi:apa_facturata_4000000001"]
    assert [(s["state"], s["sum"]) for s in stats] == [(13.0, 13.0), (14.89, 27.89)]
    meta, stats = by_id["veolia_vrsi:pret_mc_4000000001"]
    assert meta["has_sum"] is False
    assert meta["unit_of_measurement"] == "RON/m³"
    assert meta["mean_type"] is StatisticMeanType.ARITHMETIC
    assert [(s["start"].strftime("%Y-%m"), s["mean"], s["min"], s["max"]) for s in stats] == [
        ("2026-09", 17.36, 17.36, 17.36), ("2026-10", 17.36, 17.36, 17.36),
    ]
