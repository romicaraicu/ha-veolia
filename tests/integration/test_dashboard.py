"""Dashboard-ul inclus folosește doar entități care există și template-uri valide."""

from __future__ import annotations

from pathlib import Path

import yaml

from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from custom_components.veolia_vrsi.statistics import (
    billed_statistic_id,
    cost_statistic_id,
    price_statistic_id,
    statistic_id,
)

from .conftest import CODE
from .test_setup import setup_entry

ROOT = Path(__file__).parent.parent.parent
PLACEHOLDER = "4000000000"


def _load(name: str) -> dict:
    return yaml.safe_load((ROOT / "dashboard" / name).read_text().replace(PLACEHOLDER, CODE))


def _walk(node, entities: list[str], markdown: list[str], stats: list[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "markdown":
            markdown.append(node["content"])
        if node.get("type") == "statistics-graph":
            stats.extend(node["entities"])
        for value in node.values():
            _walk(value, entities, markdown, stats)
    elif isinstance(node, list):
        for value in node:
            _walk(value, entities, markdown, stats)
    elif isinstance(node, str) and node.startswith(
        ("sensor.veolia_vrsi_", "binary_sensor.veolia_vrsi_", "button.veolia_vrsi_")
    ):
        entities.append(node)


async def test_dashboard_entities_exist(hass: HomeAssistant, mock_bridge) -> None:
    await setup_entry(hass)
    entities: list[str] = []
    markdown: list[str] = []
    stats: list[str] = []
    _walk(_load("veolia_dashboard.yaml"), entities, markdown, stats)

    assert entities, "dashboard-ul nu folosește nicio entitate"
    for entity_id in entities:
        assert hass.states.get(entity_id) is not None, entity_id
    assert stats == [
        statistic_id(CODE),
        statistic_id(CODE),
        price_statistic_id(CODE),
        statistic_id(CODE),
        billed_statistic_id(CODE),
        cost_statistic_id(CODE),
    ]
    for content in markdown:
        rendered = Template(content, hass).async_render(parse_result=False)
        assert "None" not in rendered
    meters = next(m for m in markdown if "Contoare de pe ultima factură" in m)
    rendered = Template(meters, hass).async_render(parse_result=False)
    assert "22AA000001" in rendered and "I23AA000009" in rendered
    yearly = next(m for m in markdown if "Facturi pe an" in m)
    rendered = Template(yearly, hass).async_render(parse_result=False)
    assert "| 2026 | 484.28 | 27.89 | 17.36 | 2 |" in rendered
    # tabelul markdown nu are voie să aibă rânduri goale între antet și rânduri
    assert "|---|---:|---:|---:|---:|\n| 2026 |" in rendered


def test_generator_replaces_placeholder(tmp_path) -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "genereaza_dashboard.py"), CODE, str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    out = tmp_path / f"veolia_{CODE}.yaml"
    assert out.exists(), result.stdout
    text = out.read_text()
    assert PLACEHOLDER not in text
    assert f"sensor.veolia_vrsi_{CODE}_total_de_plata" in text
