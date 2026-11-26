"""Teste pentru senzori, senzori binari și buton."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .conftest import CODE
from .test_setup import setup_entry

S = f"sensor.veolia_vrsi_{CODE}"
B = f"binary_sensor.veolia_vrsi_{CODE}"


async def test_entities(hass: HomeAssistant, mock_bridge, freezer) -> None:
    freezer.move_to("2026-11-24 10:00:00+02:00")
    await setup_entry(hass)
    st = lambda key: hass.states.get(f"{S}_{key}")  # noqa: E731

    loc = st("loc_consum")
    assert loc.state.startswith("STR. EXEMPLU")
    assert loc.attributes["cod_loc_consum"] == CODE
    assert loc.attributes["cod_client"] == "10000001"
    assert loc.attributes["contoare"] == ["22AA000001"]
    assert loc.attributes["contract"] == "7000000001"

    last = st("consum_ultima_luna")
    assert last.state == "14.0"
    assert last.attributes["unit_of_measurement"] == "m³"
    assert last.attributes["device_class"] == "water"
    assert "state_class" not in last.attributes
    assert len(last.attributes["istoric"]) == 3
    assert last.attributes["istoric"][0]["luna"] == "2026-10"
    assert last.attributes["consum_anual"] == {"2026": 27.0, "2025": 9.0}

    assert st("consum_an_curent").state == "27.0"
    assert st("ultimul_index").state == "419.0"
    assert st("ultimul_index").attributes["contor_smart"] is True

    assert st("total_de_plata").state == "258.54"
    assert st("total_de_plata").attributes["unit_of_measurement"] == "RON"
    assert st("facturi_neplatite").state == "1"
    assert st("facturi_neplatite").attributes["facturi"][0]["numar"] == "VRS000000003"
    assert st("facturi_platite").state == "2"
    assert st("facturi_platite").attributes["total_pe_an"] == {"2026": 120.0, "2025": 95.1}
    assert st("ultima_factura").state == "258.54"
    assert st("urmatoarea_scadenta").state == "2026-11-18"
    assert st("ultima_plata").state == "120.0"
    assert st("ultima_plata").attributes["data"] == "2026-10-07"

    assert st("perioada_index").state == "21–25 nov. 2026"
    assert st("perioada_index_inceput").state == "2026-11-21"
    assert st("perioada_index_sfarsit").state == "2026-11-25"

    window = hass.states.get(f"{B}_perioada_index_activa")
    assert window.state == "off"
    assert window.attributes["contor_smart"] is True
    assert hass.states.get(f"{B}_factura_restanta").state == "on"


async def test_meterless_location_entities(hass: HomeAssistant, mock_bridge) -> None:
    await setup_entry(hass, locations=["4000000002"])
    s2 = "sensor.veolia_vrsi_4000000002"
    assert hass.states.get(f"{s2}_ultimul_index").state == "unknown"
    assert hass.states.get(f"{s2}_perioada_index").state == "unknown"
    assert hass.states.get(f"{s2}_facturi_neplatite").state == "0"
    assert hass.states.get(f"{s2}_consum_an_curent").state == "0.0"


async def test_refresh_button(hass: HomeAssistant, mock_bridge) -> None:
    await setup_entry(hass)
    calls = mock_bridge.get_snapshot.await_count
    await hass.services.async_call(
        "button", "press", {"entity_id": f"button.veolia_vrsi_{CODE}_actualizare"}, blocking=True
    )
    await hass.async_block_till_done()
    assert mock_bridge.get_snapshot.await_count == calls + 1


async def test_device(hass: HomeAssistant, mock_bridge) -> None:
    from homeassistant.helpers import device_registry as dr

    entry = await setup_entry(hass)
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert ("veolia_vrsi", CODE) in device.identifiers
    assert device.name.startswith("Veolia STR. EXEMPLU")
    assert device.manufacturer == "Veolia România Soluții Integrate"


async def test_refresh_button_stays_available_when_update_fails(hass: HomeAssistant, mock_bridge) -> None:
    from custom_components.veolia_vrsi.api import VeoliaBlockedError

    entry = await setup_entry(hass)
    mock_bridge.get_snapshot.side_effect = VeoliaBlockedError("blocat")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(f"sensor.veolia_vrsi_{CODE}_total_de_plata").state == "unavailable"
    assert hass.states.get(f"button.veolia_vrsi_{CODE}_actualizare").state != "unavailable"


async def test_price_sensors(hass: HomeAssistant, mock_bridge) -> None:
    await setup_entry(hass)
    st = lambda key: hass.states.get(f"{S}_{key}")  # noqa: E731
    assert st("tarif_apa").state == "7.26"
    assert st("tarif_apa").attributes["unit_of_measurement"] == "RON/m³"
    assert st("tarif_canalizare").state == "10.48"
    price = st("pret_mc_facturat")
    assert price.state == "17.36"
    assert price.attributes["factura"] == "VRS000000003"
    assert [h["luna"] for h in price.attributes["istoric"]] == ["2026-10", "2026-09"]
    assert price.attributes["pret_pe_an"] == {
        "2026": {"pret_mc": 17.36, "total": 484.28, "m3": 27.89, "facturi": 2}}
    assert st("cost_efectiv_mc").state == "23.5"
    assert st("apa_facturata").state == "14.89"
    assert st("apa_facturata").attributes["unit_of_measurement"] == "m³"
    assert st("diferenta_facturata").state == "3.89"


async def test_meter_sensors_from_invoices(hass: HomeAssistant, mock_bridge) -> None:
    await setup_entry(hass)
    own = hass.states.get(f"{S}_contor_22aa000001_consum")
    condo = hass.states.get(f"{S}_contor_i23aa000009_consum")
    assert own.state == "11.0"
    assert own.attributes["tip"] == "individual"
    assert "22AA000001" in own.attributes["friendly_name"]
    assert own.attributes["friendly_name"].endswith("(individual)")
    assert condo.state == "102.0"
    assert condo.attributes["tip"] == "condominiu"
    assert condo.attributes["index_nou"] == 3355.0
    assert hass.states.get(f"{S}_contor_i23aa000009_index").state == "3355.0"


async def test_new_meter_on_invoice_adds_entities(hass: HomeAssistant, mock_bridge) -> None:
    entry = await setup_entry(hass)
    assert hass.states.get(f"{S}_contor_22aa000002_consum") is None
    detail = mock_bridge.snapshot_data["accounts"]["10000001"]["invoice_details"]["VRS000000003"]
    detail["meters"].append({
        "serial": "22AA000002", "kind": "individual", "index_new": 12.0, "index_old": 10.0,
        "consumption": 2.0, "method": "citire", "reason": None, "date": "2026-10-28",
    })
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(f"{S}_contor_22aa000002_consum").state == "2.0"


async def test_location_without_invoice_details_has_no_meter_entities(hass: HomeAssistant, mock_bridge) -> None:
    await setup_entry(hass, locations=["4000000002"])
    s2 = "sensor.veolia_vrsi_4000000002"
    assert hass.states.get(f"{s2}_pret_mc_facturat").state == "unknown"
    assert not [s for s in hass.states.async_entity_ids("sensor") if "_contor_" in s]
