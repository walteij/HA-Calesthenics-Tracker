"""Validate the shipped Lovelace and script examples."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from homeassistant.components.script.config import async_validate_config_item
from homeassistant.core import HomeAssistant

from custom_components.calisthenics_tracker.button import BUTTONS
from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES
from custom_components.calisthenics_tracker.sensor import SENSORS

EXAMPLES = Path(__file__).parents[1] / "examples"


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


def test_dashboard_uses_only_entities_provided_by_the_integration() -> None:
    dashboard = yaml.safe_load(
        (EXAMPLES / "calisthenics_dashboard.yaml").read_text(encoding="utf-8")
    )
    assert dashboard["views"]
    expected = (
        {f"sensor.calisthenics_{description.key}" for description in SENSORS}
        | {
            f"sensor.calisthenics_progress_{definition.exercise_id}"
            for definition in WORKBOOK_EXERCISES
        }
        | {f"button.calisthenics_{description.key}" for description in BUTTONS}
    )
    assert _dashboard_entities(dashboard) <= expected
    card_types = _card_types(dashboard)
    assert {
        "tile",
        "button",
        "entities",
        "statistics-graph",
        "history-graph",
        "markdown",
        "grid",
    } <= card_types


def test_parameterized_scripts_call_existing_actions() -> None:
    scripts = yaml.safe_load(
        (EXAMPLES / "calisthenics_tracker_scripts.yaml").read_text(encoding="utf-8")
    )
    expected_actions = {
        "calisthenics_tracker.start_workout",
        "calisthenics_tracker.suggest_workout",
        "calisthenics_tracker.complete_workout",
        "calisthenics_tracker.log_exercise",
        "calisthenics_tracker.add_body_measurement",
    }
    assert {
        script["sequence"][0]["action"] for script in scripts.values()
    } == expected_actions
    assert {"session_type"} <= scripts["calisthenics_start_workout"]["fields"].keys()
    assert {
        "exercise_id",
        "variant",
        "sets",
        "rir",
        "pain_score",
    } <= scripts["calisthenics_log_exercise"]["fields"].keys()
    assert "measurement" in scripts["calisthenics_add_body_measurement"]["fields"]
    assert {
        "calisthenics_tracker.suggest_workout",
        "persistent_notification.create",
    } <= {
        action["action"]
        for action in scripts["calisthenics_suggest_workout"]["sequence"]
    }


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
