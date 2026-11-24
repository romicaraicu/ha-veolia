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
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .parser import LocationData

_LOGGER = logging.getLogger(__name__)


def statistic_id(code: str) -> str:
    return f"{DOMAIN}:consum_apa_{code}"


def monthly_rows(
    location: LocationData, tz: tzinfo, base: float = 0.0
) -> list[tuple[datetime, float, float]]:
    """(început lună, consum lună, sumă cumulată pornind de la `base`), cronologic."""
    rows: list[tuple[datetime, float, float]] = []
    total = base
    for month, value in sorted(location.monthly_consumption().items()):
        year, mon = (int(x) for x in month.split("-"))
        total = round(total + value, 3)
        rows.append((datetime(year, mon, 1, tzinfo=tz), float(value), total))
    return rows


async def _async_stored_sum_before(hass: HomeAssistant, stat_id: str, start: datetime) -> float:
    """Suma deja salvată înainte de `start` (0 dacă nu există).

    Dacă portalul întoarce la un moment dat un istoric mai scurt, rândurile noi
    continuă suma celor vechi în loc să o ia de la zero.
    """
    if "recorder" not in hass.config.components:
        return 0.0
    stats = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2000, 1, 1, tzinfo=start.tzinfo),
        start,
        {stat_id},
        "hour",
        None,
        {"sum"},
    )
    rows = stats.get(stat_id) or []
    return float(rows[-1].get("sum") or 0.0) if rows else 0.0


async def async_import_statistics(
    hass: HomeAssistant, locations: dict[str, LocationData]
) -> None:
    """Scrie (sau rescrie) istoricul lunar al fiecărui loc de consum."""
    tz = dt_util.get_default_time_zone()
    for code, location in locations.items():
        rows = monthly_rows(location, tz)
        if not rows:
            continue
        base = await _async_stored_sum_before(hass, statistic_id(code), rows[0][0])
        if base:
            rows = monthly_rows(location, tz, base)
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
