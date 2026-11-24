"""Statistici externe cu consumul lunar, pentru cardurile „Statistics graph”.

Perioadele de citire nu coincid cu lunile calendaristice: fiecare perioadă se
atribuie lunii în care se termină și se scrie la ora 00:00 din prima zi a lunii.
"""

from __future__ import annotations

from datetime import datetime, tzinfo
import logging

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .parser import LocationData

_LOGGER = logging.getLogger(__name__)


def statistic_id(code: str) -> str:
    return f"{DOMAIN}:consum_apa_{code}"


def monthly_rows(location: LocationData, tz: tzinfo) -> list[tuple[datetime, float, float]]:
    """(început lună, consum lună, sumă cumulată), în ordine cronologică."""
    rows: list[tuple[datetime, float, float]] = []
    total = 0.0
    for month, value in sorted(location.monthly_consumption().items()):
        year, mon = (int(x) for x in month.split("-"))
        total = round(total + value, 3)
        rows.append((datetime(year, mon, 1, tzinfo=tz), float(value), total))
    return rows


async def async_import_statistics(
    hass: HomeAssistant, locations: dict[str, LocationData]
) -> None:
    """Scrie (sau rescrie) istoricul lunar al fiecărui loc de consum."""
    tz = dt_util.get_default_time_zone()
    for code, location in locations.items():
        rows = monthly_rows(location, tz)
        if not rows:
            continue
        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"Consum apă {location.address}",
            source=DOMAIN,
            statistic_id=statistic_id(code),
            unit_class="volume",
            unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        )
        stats = [StatisticData(start=start, state=value, sum=total) for start, value, total in rows]
        async_add_external_statistics(hass, metadata, stats)
        _LOGGER.debug("Statistici importate pentru %s: %d luni", code, len(stats))
