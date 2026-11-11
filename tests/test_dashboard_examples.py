"""Validate the shipped Lovelace and script examples."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from homeassistant.components.script.config import async_validate_config_item
from homeassistant.core import HomeAssistant

from custom_components.calisthenics_tracker.button import BUTTONS
from custom_components.calisthenics_tracker.const import (
    DOMAIN,
    SERVICE_ADD_BODY_MEASUREMENT,
    SERVICE_START,
)
from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES
from custom_components.calisthenics_tracker.select import SUGGESTION_FOCUS
from custom_components.calisthenics_tracker.sensor import SENSORS, SUGGESTION_SENSORS

EXAMPLES = Path(__file__).parents[1] / "examples"
HELPERS = {
    "input_number.calisthenics_invoer_gewicht",
    "input_number.calisthenics_invoer_taille",
}


def _load(name: str) -> Any:
    return yaml.safe_load((EXAMPLES / name).read_text(encoding="utf-8"))


def _dashboard_entities(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = {
            item
            for key, child in value.items()
            if key == "entity" and isinstance(item := child, str)
        }
        for child in value.values():
            found.update(_dashboard_entities(child))
        return found
    if isinstance(value, list):
        return set().union(*(_dashboard_entities(item) for item in value))
    return set()


def _card_types(value: Any) -> set[str]:
    if isinstance(value, dict):
        types = {value["type"]} if isinstance(value.get("type"), str) else set()
        for child in value.values():
            types.update(_card_types(child))
        return types
    if isinstance(value, list):
        return set().union(*(_card_types(item) for item in value))
    return set()


def _json_paths(value: Any, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return set()
    paths: set[str] = set()
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.add(path)
        paths.update(_json_paths(child, path))
    return paths


def test_dashboard_uses_only_integration_entities_and_documented_helpers() -> None:
    dashboard = _load("calisthenics_dashboard.yaml")
    scripts = _load("calisthenics_tracker_scripts.yaml")
    assert dashboard["type"] == "sections"
    assert dashboard["sections"]
    integration_entities = (
        {f"sensor.calisthenics_{description.key}" for description in SENSORS}
        | {
            f"sensor.calisthenics_progress_{definition.exercise_id}"
            for definition in WORKBOOK_EXERCISES
        }
        | {f"button.calisthenics_{description.key}" for description in BUTTONS}
        | {
            f"sensor.calisthenics_{description.key}"
            for description in SUGGESTION_SENSORS
        }
        | {f"select.calisthenics_{SUGGESTION_FOCUS.key}"}
    )
    example_scripts = {f"script.{script_id}" for script_id in scripts}
    used = _dashboard_entities(dashboard)
    assert used <= integration_entities | example_scripts | HELPERS
    assert example_scripts <= used
    assert "select.calisthenics_suggestion_focus" in used
    assert {
        "sections",
        "heading",
        "tile",
        "markdown",
        "statistics-graph",
        "history-graph",
        "custom:button-card",
    } <= _card_types(dashboard)


def test_scripts_call_existing_actions_with_documented_helpers() -> None:
    scripts = _load("calisthenics_tracker_scripts.yaml")
    tracker_actions = {
        action["action"]
        for script in scripts.values()
        for action in script["sequence"]
        if action["action"].startswith(f"{DOMAIN}.")
    }
    assert tracker_actions == {
        f"{DOMAIN}.{SERVICE_START}",
        f"{DOMAIN}.{SERVICE_ADD_BODY_MEASUREMENT}",
    }
    session_types = {
        script["sequence"][0]["data"]["session_type"]
        for script in scripts.values()
        if script["sequence"][0]["action"] == f"{DOMAIN}.{SERVICE_START}"
    }
    assert session_types == {"A", "B"}
    measurement = scripts["calisthenics_meting_opslaan"]["sequence"][0]["data"]
    assert set(measurement) == {"weight_kg", "waist_cm"}
    for helper in HELPERS:
        assert any(helper in template for template in measurement.values())


def test_translation_files_match_the_source_strings() -> None:
    integration = EXAMPLES.parent / "custom_components" / "calisthenics_tracker"
    source = json.loads((integration / "strings.json").read_text(encoding="utf-8"))
    assert "button" in source["entity"]
    assert "button" not in source
    source_paths = _json_paths(source)
    for language in ("en", "nl"):
        translation = json.loads(
            (integration / "translations" / f"{language}.json").read_text(
                encoding="utf-8"
            )
        )
        assert _json_paths(translation) == source_paths


@pytest.mark.asyncio
async def test_scripts_pass_home_assistant_script_config_validation(
    tmp_path: Path,
) -> None:
    scripts: dict[str, Any] = yaml.safe_load(
        (EXAMPLES / "calisthenics_tracker_scripts.yaml").read_text(encoding="utf-8")
    )
    hass = HomeAssistant(str(tmp_path))
    for script_id, config in scripts.items():
        validated = await async_validate_config_item(hass, script_id, config)
        assert validated is not None, script_id
