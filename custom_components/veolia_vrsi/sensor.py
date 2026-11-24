"""Senzori Veolia VRSI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import VeoliaConfigEntry
from .const import HISTORY_LIMIT
from .entity import VeoliaEntity
from .parser import LocationData, iso

CURRENCY = "RON"


@dataclass(frozen=True, kw_only=True)
class VeoliaSensorDescription(SensorEntityDescription):
    value_fn: Callable[[LocationData, date], Any]
    attrs_fn: Callable[[LocationData, date], dict[str, Any]] | None = None


def _location_attrs(d: LocationData, today: date) -> dict[str, Any]:
    contract = d.contract or {}
    return {
        "cod_client": d.client_code,
        "cod_loc_consum": d.code,
        "instalatie": d.installation,
        "contoare": d.meters,
        "contract": contract.get("ContractNumber"),
        "tip_contract": contract.get("Type"),
        "inceput_contract": contract.get("ContractStartDate"),
    }


def _last_period_attrs(d: LocationData, today: date) -> dict[str, Any]:
    last = d.last_period
    return {
        **(last.as_attr() if last else {}),
        "consum_anual": d.yearly_consumption(),
        "istoric": [p.as_attr() for p in d.periods[:HISTORY_LIMIT]],
    }


def _index_attrs(d: LocationData, today: date) -> dict[str, Any]:
    return {
        "data": iso(d.last_index_date),
        "contor": d.meter,
        "contor_smart": d.is_smart,
    }


def _total_attrs(d: LocationData, today: date) -> dict[str, Any]:
    return {
        "restant": d.overdue_amount(today),
        "urmatoarea_scadenta": iso(d.next_due_date(today)),
        "facturi_neplatite": len(d.unpaid),
    }


def _unpaid_attrs(d: LocationData, today: date) -> dict[str, Any]:
    return {
        "total_rest_plata": round(sum(i.balance for i in d.unpaid), 2),
        "restant": d.overdue_amount(today),
        "facturi": [i.as_attr() for i in d.unpaid],
    }


def _paid_attrs(d: LocationData, today: date) -> dict[str, Any]:
    return {
        "facturi": [i.as_attr() for i in d.paid_recent(today)],
        "total_pe_an": d.paid_yearly_totals(),
    }


def _last_invoice_attrs(d: LocationData, today: date) -> dict[str, Any]:
    return d.last_invoice.as_attr() if d.last_invoice else {}


def _payment_attrs(d: LocationData, today: date) -> dict[str, Any]:
    return d.last_payment.as_attr() if d.last_payment else {}


def _reading_attrs(d: LocationData, today: date) -> dict[str, Any]:
    return {
        "inceput": iso(d.reading_start),
        "sfarsit": iso(d.reading_end),
        "contor_smart": d.is_smart,
    }


def _water(key: str, value_fn, attrs_fn=None) -> VeoliaSensorDescription:
    return VeoliaSensorDescription(
        key=key,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=0,
        value_fn=value_fn,
        attrs_fn=attrs_fn,
    )


def _money(key: str, value_fn, attrs_fn=None) -> VeoliaSensorDescription:
    return VeoliaSensorDescription(
        key=key,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY,
        suggested_display_precision=2,
        value_fn=value_fn,
        attrs_fn=attrs_fn,
    )


SENSORS: tuple[VeoliaSensorDescription, ...] = (
    VeoliaSensorDescription(
        key="loc_consum", icon="mdi:home-map-marker",
        value_fn=lambda d, t: d.address[:255], attrs_fn=_location_attrs,
    ),
    _water(
        "consum_ultima_luna",
        lambda d, t: d.last_period.consumption if d.last_period else None,
        _last_period_attrs,
    ),
    _water("consum_an_curent", lambda d, t: d.current_year_consumption(t)),
    _water("ultimul_index", lambda d, t: d.last_index, _index_attrs),
    _money("total_de_plata", lambda d, t: d.total_to_pay or 0.0, _total_attrs),
    VeoliaSensorDescription(
        key="facturi_neplatite", icon="mdi:file-document-alert",
        value_fn=lambda d, t: len(d.unpaid), attrs_fn=_unpaid_attrs,
    ),
    VeoliaSensorDescription(
        key="facturi_platite", icon="mdi:file-document-check",
        value_fn=lambda d, t: len(d.paid_recent(t)), attrs_fn=_paid_attrs,
    ),
    _money(
        "ultima_factura",
        lambda d, t: d.last_invoice.total if d.last_invoice else None,
        _last_invoice_attrs,
    ),
    VeoliaSensorDescription(
        key="urmatoarea_scadenta", device_class=SensorDeviceClass.DATE,
        value_fn=lambda d, t: d.next_due_date(t),
    ),
    _money(
        "ultima_plata",
        lambda d, t: d.last_payment.amount if d.last_payment else None,
        _payment_attrs,
    ),
    VeoliaSensorDescription(
        key="perioada_index", icon="mdi:calendar-range",
        value_fn=lambda d, t: d.reading_label, attrs_fn=_reading_attrs,
    ),
    VeoliaSensorDescription(
        key="perioada_index_inceput", device_class=SensorDeviceClass.DATE,
        value_fn=lambda d, t: d.reading_start,
    ),
    VeoliaSensorDescription(
        key="perioada_index_sfarsit", device_class=SensorDeviceClass.DATE,
        value_fn=lambda d, t: d.reading_end,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VeoliaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        VeoliaSensor(coordinator, code, description)
        for code in coordinator.data
        for description in SENSORS
    )


class VeoliaSensor(VeoliaEntity, SensorEntity):
    entity_description: VeoliaSensorDescription

    def __init__(self, coordinator, code: str, description: VeoliaSensorDescription) -> None:
        super().__init__(coordinator, code, description.key, "sensor")
        self.entity_description = description
        self._update_values()

    def _update_values(self) -> None:
        data = self.location
        if data is None:
            return
        today = dt_util.now().date()
        self._attr_native_value = self.entity_description.value_fn(data, today)
        attrs_fn = self.entity_description.attrs_fn
        self._attr_extra_state_attributes = attrs_fn(data, today) if attrs_fn else {}

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_values()
        super()._handle_coordinator_update()
