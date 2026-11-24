"""Statistici externe lunare, pentru cardurile „Statistics graph”.

Perioadele de citire nu coincid cu lunile calendaristice: fiecare perioadă (sau
factură) se atribuie lunii în care se termină și se scrie la ora 00:00 din prima
zi a lunii. Statisticile se rescriu la fiecare actualizare, cu aceleași valori.
"""

from __future__ import annotations

from datetime import datetime, tzinfo
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN
from .parser import LocationData

_LOGGER = logging.getLogger(__name__)

PRICE_UNIT = f"RON/{UnitOfVolume.CUBIC_METERS}"


def statistic_id(code: str) -> str:
    return f"{DOMAIN}:consum_apa_{code}"


def meter_statistic_id(serial: str) -> str:
    return f"{DOMAIN}:contor_{slugify(serial)}"


def billed_statistic_id(code: str) -> str:
    return f"{DOMAIN}:apa_facturata_{code}"


def price_statistic_id(code: str) -> str:
    return f"{DOMAIN}:pret_mc_{code}"


def _month_start(month: str, tz: tzinfo) -> datetime:
    year, mon = (int(x) for x in month.split("-"))
    return datetime(year, mon, 1, tzinfo=tz)


def _sum_rows(
    monthly: dict[str, float], tz: tzinfo, base: float = 0.0
) -> list[tuple[datetime, float, float]]:
    rows: list[tuple[datetime, float, float]] = []
    total = base
    for month, value in sorted(monthly.items()):
        total = round(total + value, 3)
        rows.append((_month_start(month, tz), float(value), total))
    return rows


def monthly_rows(
    location: LocationData, tz: tzinfo, base: float = 0.0
) -> list[tuple[datetime, float, float]]:
    """(început lună, consum lună, sumă cumulată pornind de la `base`), cronologic."""
    return _sum_rows(location.monthly_consumption(), tz, base)


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


async def _async_import_sum(
    hass: HomeAssistant, stat_id: str, name: str, monthly: dict[str, float], tz: tzinfo
) -> None:
    rows = _sum_rows(monthly, tz)
    if not rows:
        return
    base = await _async_stored_sum_before(hass, stat_id, rows[0][0])
    if base:
        rows = _sum_rows(monthly, tz, base)
    metadata = StatisticMetaData(
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
        name=name,
        source=DOMAIN,
        statistic_id=stat_id,
        unit_class="volume",
        unit_of_measurement=UnitOfVolume.CUBIC_METERS,
    )
    async_add_external_statistics(
        hass,
        metadata,
        [StatisticData(start=start, state=value, sum=total) for start, value, total in rows],
    )


def _import_price(
    hass: HomeAssistant, stat_id: str, name: str, monthly: dict[str, float], tz: tzinfo
) -> None:
    if not monthly:
        return
    metadata = StatisticMetaData(
        mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=False,
        name=name,
        source=DOMAIN,
        statistic_id=stat_id,
        unit_class=None,
        unit_of_measurement=PRICE_UNIT,
    )
    async_add_external_statistics(
        hass,
        metadata,
        [
            StatisticData(start=_month_start(month, tz), mean=price, min=price, max=price)
            for month, price in sorted(monthly.items())
        ],
    )


async def async_import_statistics(
    hass: HomeAssistant, locations: dict[str, LocationData]
) -> None:
    """Scrie (sau rescrie) istoricul lunar al fiecărui loc de consum și contor."""
    tz = dt_util.get_default_time_zone()
    for code, location in locations.items():
        address = location.address
        await _async_import_sum(
            hass, statistic_id(code), f"Consum apă {address}", location.monthly_consumption(), tz
        )
        for serial, reading in location.meter_readings().items():
            await _async_import_sum(
                hass,
                meter_statistic_id(serial),
                f"Contor {serial} ({reading.kind})",
                location.meter_monthly(serial),
                tz,
            )
        await _async_import_sum(
            hass, billed_statistic_id(code), f"Apă facturată {address}", location.billed_monthly(), tz
        )
        _import_price(
            hass, price_statistic_id(code), f"Preț pe m³ {address}", location.price_monthly(), tz
        )
        _LOGGER.debug("Statistici importate pentru %s", code)
