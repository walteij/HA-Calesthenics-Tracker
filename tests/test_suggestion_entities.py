"""Native workout suggestion select and sensor entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import State

from custom_components.calisthenics_tracker.const import (
    DOMAIN,
    PLATFORMS,
    SUGGESTION_DEVICE_NAME,
    WORKOUT_FOCI,
)
from custom_components.calisthenics_tracker.coordinator import TrackerCoordinator
from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES
from custom_components.calisthenics_tracker.models import Profile, TrackerData
from custom_components.calisthenics_tracker.select import SuggestionFocusSelect
from custom_components.calisthenics_tracker.sensor import (
    SUGGESTION_SENSORS,
    WorkoutSuggestionSensor,
)
from custom_components.calisthenics_tracker.workout_plans import suggest_workout

EXERCISE_KEYS = {
    "exercise_id",
    "name",
    "prescription",
    "target_sets",
    "minimum_repetitions",
    "maximum_repetitions",
    "unit",
    "tutorial_url",
    "tutorial_label",
}


@dataclass
class _MemoryStorage:
    data: TrackerData

    async def async_save(self, data: TrackerData) -> None:
        self.data = data


def _coordinator(
    definitions: tuple = WORKBOOK_EXERCISES, level: str = "beginner"
) -> TrackerCoordinator:
    profile = Profile(
        name="Walter",
        start_date=date(2026, 11, 8),
        current_level=level,
        goal="Strength",
        target_sessions_per_week=3,
        daily_step_target=8000,
    )
    data = TrackerData(profile, exercise_definitions=definitions)
    return TrackerCoordinator(object(), _MemoryStorage(data), data)


def _entities(
    coordinator: TrackerCoordinator,
) -> tuple[SuggestionFocusSelect, dict[str, WorkoutSuggestionSensor]]:
    suggestion = coordinator.workout_suggestion
    select = SuggestionFocusSelect(suggestion, "entry")
    sensors = {
        description.key: WorkoutSuggestionSensor(suggestion, "entry", description)
        for description in SUGGESTION_SENSORS
    }
    return select, sensors


async def _add_to_hass(*entities: object) -> dict[str, int]:
    writes: dict[str, int] = {}
    for entity in entities:
        writes[entity.entity_id] = 0

        def _write(entity_id: str = entity.entity_id) -> None:
            writes[entity_id] += 1

        entity.async_write_ha_state = _write
        entity.async_get_last_state = AsyncMock(return_value=None)
        await entity.async_added_to_hass()
    return writes


def test_select_platform_is_forwarded_by_config_entry() -> None:
    assert "select" in {platform.value for platform in PLATFORMS}


def test_entities_use_requested_ids_and_share_one_device() -> None:
    select, sensors = _entities(_coordinator())

    assert select.entity_id == "select.calisthenics_suggestion_focus"
    assert select.options == list(WORKOUT_FOCI)
    assert {sensor.entity_id for sensor in sensors.values()} == {
        "sensor.calisthenics_suggestion_title",
        "sensor.calisthenics_suggestion_level",
        "sensor.calisthenics_suggestion_format",
        "sensor.calisthenics_suggestion_note",
        "sensor.calisthenics_suggestion_exercise_count",
        "sensor.calisthenics_suggestion_exercises",
    }
    devices = [select.device_info, *(s.device_info for s in sensors.values())]
    assert all(device == devices[0] for device in devices)
    assert devices[0]["identifiers"] == {(DOMAIN, "entry_workout_suggestion")}
    assert devices[0]["name"] == SUGGESTION_DEVICE_NAME
    assert len({select.unique_id, *(s.unique_id for s in sensors.values())}) == 7


def test_sensors_are_populated_on_load_with_the_default_focus() -> None:
    select, sensors = _entities(_coordinator())
    expected = suggest_workout("core_strength", "beginner", WORKBOOK_EXERCISES)

    assert select.current_option == "core_strength"
    assert sensors["suggestion_title"].native_value == expected["title"]
    assert sensors["suggestion_level"].native_value == "beginner"
    assert sensors["suggestion_format"].native_value == expected["format"]
    assert sensors["suggestion_note"].native_value == ""
    assert sensors["suggestion_exercise_count"].native_value == 4
    assert sensors["suggestion_exercise_count"].state_class is None
    assert sensors["suggestion_exercise_count"].native_unit_of_measurement is None
    assert sensors["suggestion_exercises"].native_value == "4"
    assert all(sensor.available for sensor in sensors.values())


def test_exercises_attribute_exposes_the_full_structured_suggestion() -> None:
    _, sensors = _entities(_coordinator())
    exercises = sensors["suggestion_exercises"].extra_state_attributes["exercises"]

    assert [exercise["exercise_id"] for exercise in exercises] == [
        "beginner_dead_bug",
        "beginner_plank",
        "beginner_side_plank",
        "beginner_glute_bridge",
    ]
    assert all(set(exercise) == EXERCISE_KEYS for exercise in exercises)
    assert exercises[0]["name"] == "Dead bug"
    assert sensors["suggestion_title"].extra_state_attributes is None
    assert "exercises" in WorkoutSuggestionSensor._unrecorded_attributes


@pytest.mark.asyncio
async def test_selecting_a_focus_updates_all_suggestion_entities() -> None:
    select, sensors = _entities(_coordinator())
    writes = await _add_to_hass(select, *sensors.values())

    await select.async_select_option("fat_loss_support")

    expected = suggest_workout("fat_loss_support", "beginner", WORKBOOK_EXERCISES)
    assert select.current_option == "fat_loss_support"
    assert sensors["suggestion_title"].native_value == expected["title"]
    assert sensors["suggestion_note"].native_value == expected["note"]
    assert sensors["suggestion_exercise_count"].native_value == 5
    assert sensors["suggestion_exercises"].extra_state_attributes == {
        "focus": "fat_loss_support",
        "exercises": expected["exercises"],
    }
    assert set(writes.values()) == {1}


@pytest.mark.asyncio
async def test_selecting_the_current_focus_does_not_rewrite_states() -> None:
    select, sensors = _entities(_coordinator())
    writes = await _add_to_hass(select, *sensors.values())

    await select.async_select_option("core_strength")

    assert set(writes.values()) == {0}


@pytest.mark.asyncio
async def test_select_rejects_unknown_focus() -> None:
    select, _ = _entities(_coordinator())

    with pytest.raises(ValueError):
        await select.async_select_option("marathon")
    assert select.current_option == "core_strength"


@pytest.mark.asyncio
async def test_select_restores_last_focus_after_restart() -> None:
    select, sensors = _entities(_coordinator())
    select.async_write_ha_state = lambda: None
    select.async_get_last_state = AsyncMock(
        return_value=State(select.entity_id, "conditioning")
    )

    await select.async_added_to_hass()

    assert select.current_option == "conditioning"
    assert sensors["suggestion_title"].native_value == "Conditie"


@pytest.mark.asyncio
async def test_invalid_restored_focus_keeps_the_default() -> None:
    select, _ = _entities(_coordinator())
    select.async_write_ha_state = lambda: None
    select.async_get_last_state = AsyncMock(
        return_value=State(select.entity_id, "unknown")
    )

    await select.async_added_to_hass()

    assert select.current_option == "core_strength"


@pytest.mark.asyncio
async def test_profile_level_change_refreshes_the_suggestion() -> None:
    coordinator = _coordinator()
    select, sensors = _entities(coordinator)
    writes = await _add_to_hass(select, *sensors.values())
    data = coordinator.data

    await coordinator._commit(
        replace(data, profile=replace(data.profile, current_level="advanced"))
    )

    assert sensors["suggestion_level"].native_value == "advanced"
    exercises = sensors["suggestion_exercises"].extra_state_attributes["exercises"]
    assert exercises[0]["exercise_id"] == "advanced_hanging_knee_raise"
    assert set(writes.values()) == {1}


@pytest.mark.asyncio
async def test_unloaded_entities_stop_listening() -> None:
    select, sensors = _entities(_coordinator())
    writes = await _add_to_hass(select, *sensors.values())

    for entity in (select, *sensors.values()):
        for remove in entity._on_remove or []:
            remove()
    await select.async_select_option("conditioning")

    assert set(writes.values()) == {0}


def test_sensors_are_unavailable_when_the_plan_cannot_be_built() -> None:
    _, sensors = _entities(_coordinator(definitions=()))

    for sensor in sensors.values():
        assert sensor.available is False
        assert sensor.native_value is None
        assert sensor.extra_state_attributes is None
