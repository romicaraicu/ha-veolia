"""Teste pentru importul statisticilor lunare de consum."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from unittest.mock import patch

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
    # locul fără istoric nu produce statistici
    assert mock_add.call_count == 2
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
