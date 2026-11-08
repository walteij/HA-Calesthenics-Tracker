"""Coordinator-backed action behavior in phase one."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from probatio import Invalid

from custom_components.calisthenics_tracker.const import (
    DOMAIN,
    SERVICE_ADD_BODY_MEASUREMENT,
    SERVICE_CANCEL,
    SERVICE_LOG_EXERCISE,
)
from custom_components.calisthenics_tracker.coordinator import TrackerCoordinator
from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES
from custom_components.calisthenics_tracker.models import (
    Profile,
    TrackerData,
)
from custom_components.calisthenics_tracker.services import (
    ADD_BODY_MEASUREMENT_SCHEMA,
    LOG_EXERCISE_SCHEMA,
    register_services,
    unregister_services,
)


def _profile() -> Profile:
    return Profile(
        name="Walter",
        start_date=date(2026, 11, 8),
        current_level="beginner",
        goal="Strength",
        target_sessions_per_week=3,
        daily_step_target=8000,
    )


@dataclass
class _MemoryStorage:
    data: TrackerData

    async def async_save(self, data: TrackerData) -> None:
        self.data = data


class _FakeHass:
    def __init__(self) -> None:
        self.config = type("Config", (), {"time_zone": "Europe/Amsterdam"})()
        self.services = _FakeServices()
        self.config_entries = SimpleNamespace(async_entries=lambda _domain: [])


class _FakeServices:
    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}
        self.register_calls = 0

    def has_service(self, domain: str, name: str) -> bool:
        return f"{domain}.{name}" in self.handlers

    def async_register(
        self, domain: str, name: str, handler: Any, **kwargs: Any
    ) -> None:
        key = f"{domain}.{name}"
        if key in self.handlers:
            raise AssertionError(f"Duplicate service registration: {key}")
        self.register_calls += 1
        self.handlers[key] = (handler, kwargs["schema"])

    def async_remove(self, domain: str, name: str) -> None:
        self.handlers.pop(f"{domain}.{name}", None)


@pytest.mark.asyncio
async def test_workout_start_and_complete() -> None:
    storage = _MemoryStorage(TrackerData(_profile()))
    coordinator = TrackerCoordinator(_FakeHass(), storage, storage.data)
    start_time = dt_util.utcnow() - timedelta(minutes=50)
    end_time = dt_util.utcnow() - timedelta(minutes=5)
    started = await coordinator.async_start_workout("A", start_time.isoformat())
    assert started.status == "active"
    completed = await coordinator.async_complete_workout(end_time.isoformat(), "good")
    assert completed.status == "completed"
    assert completed.duration_minutes == pytest.approx(45.0, abs=0.001)


@pytest.mark.asyncio
async def test_cancel_workout_preserves_workout_but_not_as_completed() -> None:
    storage = _MemoryStorage(
        TrackerData(_profile(), exercise_definitions=WORKBOOK_EXERCISES)
    )
    coordinator = TrackerCoordinator(_FakeHass(), storage, storage.data)
    started = await coordinator.async_start_workout(
        "A", (dt_util.utcnow() - timedelta(minutes=10)).isoformat()
    )

    cancelled = await coordinator.async_cancel_workout()

    assert cancelled.workout_id == started.workout_id
    assert cancelled.status == "cancelled"
    assert cancelled.completed_at is not None
    assert cancelled.duration_minutes is not None
    assert coordinator.active_workout is None
    assert storage.data.workouts[0].status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_workout_rejects_missing_active_workout() -> None:
    storage = _MemoryStorage(TrackerData(_profile()))
    coordinator = TrackerCoordinator(_FakeHass(), storage, storage.data)

    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_cancel_workout()

    assert err.value.translation_key == "no_active"


@pytest.mark.asyncio
async def test_rejects_duplicate_active_workout() -> None:
    storage = _MemoryStorage(TrackerData(_profile()))
    coordinator = TrackerCoordinator(_FakeHass(), storage, storage.data)
    start_time = dt_util.utcnow() - timedelta(minutes=30)
    await coordinator.async_start_workout("B", start_time.isoformat())
    with pytest.raises(ServiceValidationError):
        await coordinator.async_start_workout("A", start_time.isoformat())


@pytest.mark.asyncio
async def test_restart_preserves_active_workout() -> None:
    storage = _MemoryStorage(
        TrackerData(_profile(), exercise_definitions=WORKBOOK_EXERCISES)
    )
    coordinator = TrackerCoordinator(_FakeHass(), storage, storage.data)
    start_time = dt_util.utcnow() - timedelta(minutes=10)
    started = await coordinator.async_start_workout("B", start_time.isoformat())
    payload = storage.data.to_dict()
    restored = TrackerData.from_dict(payload)
    second = TrackerCoordinator(_FakeHass(), storage, restored)
    active = second.active_workout
    assert active is not None
    assert active.workout_id == started.workout_id


@pytest.mark.asyncio
async def test_exercise_logging_records_individual_sets_and_corrects_in_place() -> None:
    storage = _MemoryStorage(
        TrackerData(_profile(), exercise_definitions=WORKBOOK_EXERCISES)
    )
    coordinator = TrackerCoordinator(_FakeHass(), storage, storage.data)
    started = await coordinator.async_start_workout(
        "A", (dt_util.utcnow() - timedelta(minutes=10)).isoformat()
    )
    first, replaced, _workout_id = await coordinator.async_log_exercise(
        "beginner_push_up",
        "Incline push-up",
        [10, 9.5, 8],
        rir=2,
        pain_score=1,
        notes="First entry",
    )
    assert first.sets == (10, 9.5, 8)
    assert replaced is False

    correction, replaced, _workout_id = await coordinator.async_log_exercise(
        "beginner_push_up",
        "Knee push-up",
        [11, 10, 9],
        rir=3,
        pain_score=0,
        notes="Corrected variant and reps",
    )
    active = coordinator.active_workout
    assert active is not None and active.workout_id == started.workout_id
    assert replaced is True
    assert correction.variant == "Knee push-up"
    assert len(active.exercises) == 1
    assert active.exercises[0].sets == (11, 10, 9)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "translation_key"),
    [
        ("sets", [], "invalid_sets"),
        ("sets", [1, 0], "invalid_sets"),
        ("sets", [-1], "invalid_sets"),
        ("sets", [True], "invalid_sets"),
        ("sets", [float("inf")], "invalid_sets"),
        ("rir", -1, "invalid_rir"),
        ("rir", 6, "invalid_rir"),
        ("rir", 1.5, "invalid_rir"),
        ("pain_score", -1, "invalid_pain_score"),
        ("pain_score", 11, "invalid_pain_score"),
        ("pain_score", True, "invalid_pain_score"),
    ],
)
async def test_exercise_logging_rejects_invalid_values(
    field: str, value: Any, translation_key: str
) -> None:
    storage = _MemoryStorage(
        TrackerData(_profile(), exercise_definitions=WORKBOOK_EXERCISES)
    )
    coordinator = TrackerCoordinator(_FakeHass(), storage, storage.data)
    await coordinator.async_start_workout(
        "A", (dt_util.utcnow() - timedelta(minutes=5)).isoformat()
    )
    values: dict[str, Any] = {
        "exercise_id": "beginner_push_up",
        "variant": "Push-up",
        "sets": [8, 8, 8],
        "rir": 2,
        "pain_score": 0,
        "notes": "",
    }
    values[field] = value
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_log_exercise(**values)
    assert err.value.translation_key == translation_key


@pytest.mark.asyncio
async def test_exercise_logging_rejects_unknown_exercise() -> None:
    storage = _MemoryStorage(
        TrackerData(_profile(), exercise_definitions=WORKBOOK_EXERCISES)
    )
    coordinator = TrackerCoordinator(_FakeHass(), storage, storage.data)
    await coordinator.async_start_workout(
        "B", (dt_util.utcnow() - timedelta(minutes=5)).isoformat()
    )
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_log_exercise("not_in_catalog", "Push-up", [8], 2, 0)
    assert err.value.translation_key == "unknown_exercise"


@pytest.mark.asyncio
async def test_log_exercise_action_schema_and_response() -> None:
    hass = _FakeHass()
    storage = _MemoryStorage(
        TrackerData(_profile(), exercise_definitions=WORKBOOK_EXERCISES)
    )
    coordinator = TrackerCoordinator(hass, storage, storage.data)
    await coordinator.async_start_workout(
        "A", (dt_util.utcnow() - timedelta(minutes=5)).isoformat()
    )
    hass.config_entries.async_entries = lambda domain: [
        SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=coordinator)
    ]
    register_services(hass)
    handler, schema = hass.services.handlers[f"{DOMAIN}.{SERVICE_LOG_EXERCISE}"]
    call_data = schema(
        {
            "exercise_id": "beginner_push_up",
            "variant": "Push-up",
            "sets": [10, 8, 7],
            "rir": 1,
            "pain_score": 4,
        }
    )
    result = await handler(SimpleNamespace(data=call_data))
    assert result["exercise_id"] == "beginner_push_up"
    assert result["pain_warning"] is True
    assert result["replaced_existing"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sets", []),
        ("sets", [0, 3]),
        ("sets", ["8", 3]),
        ("rir", -1),
        ("rir", 6),
        ("pain_score", -1),
        ("pain_score", 11),
    ],
)
def test_log_exercise_action_schema_rejects_invalid_values(
    field: str, value: Any
) -> None:
    call_data: dict[str, Any] = {
        "exercise_id": "beginner_push_up",
        "variant": "Push-up",
        "sets": [8, 8, 8],
        "rir": 2,
        "pain_score": 0,
    }
    call_data[field] = value
    with pytest.raises(Invalid):
        LOG_EXERCISE_SCHEMA(call_data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("weight_kg", 0),
        ("weight_kg", 501),
        ("waist_cm", 301),
        ("resting_heart_rate", 0),
        ("steps", -1),
        ("steps", 1.5),
        ("sleep_hours", 24.1),
        ("calorie_intake", float("nan")),
        ("protein_grams", True),
    ],
)
def test_body_measurement_action_schema_rejects_invalid_values(
    field: str, value: Any
) -> None:
    with pytest.raises(Invalid):
        ADD_BODY_MEASUREMENT_SCHEMA({field: value})


@pytest.mark.asyncio
async def test_add_body_measurement_action_returns_persisted_id() -> None:
    hass = _FakeHass()
    storage = _MemoryStorage(TrackerData(_profile()))
    coordinator = TrackerCoordinator(hass, storage, storage.data)
    hass.config_entries.async_entries = lambda domain: [
        SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=coordinator)
    ]
    register_services(hass)
    handler, schema = hass.services.handlers[f"{DOMAIN}.{SERVICE_ADD_BODY_MEASUREMENT}"]
    call_data = schema({"weight_kg": 79.5, "steps": 8000, "sleep_hours": 7})
    result = await handler(SimpleNamespace(data=call_data))
    assert result["measurement_id"] == storage.data.body_measurements[0].measurement_id
    assert result["measured_at"]


@pytest.mark.asyncio
async def test_cancel_workout_action_returns_cancelled_status() -> None:
    hass = _FakeHass()
    storage = _MemoryStorage(TrackerData(_profile()))
    coordinator = TrackerCoordinator(hass, storage, storage.data)
    await coordinator.async_start_workout(
        "B", (dt_util.utcnow() - timedelta(minutes=5)).isoformat()
    )
    hass.config_entries.async_entries = lambda domain: [
        SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=coordinator)
    ]
    register_services(hass)
    handler, schema = hass.services.handlers[f"{DOMAIN}.{SERVICE_CANCEL}"]

    result = await handler(SimpleNamespace(data=schema({})))

    assert result["status"] == "cancelled"
    assert storage.data.workouts[0].status == "cancelled"


def test_service_registration_is_idempotent() -> None:
    hass = _FakeHass()
    register_services(hass)
    register_services(hass)
    assert hass.services.register_calls == 5
    assert len(hass.services.handlers) == 5


def test_services_are_removed_after_last_entry_unloads_and_can_reload() -> None:
    hass = _FakeHass()
    hass.config_entries.async_entries = lambda domain: [
        SimpleNamespace(entry_id="entry", state=ConfigEntryState.LOADED)
    ]
    register_services(hass)
    unregister_services(hass, "entry")
    assert hass.services.handlers == {}

    register_services(hass)
    assert len(hass.services.handlers) == 5


def test_services_remain_when_another_entry_is_still_loaded() -> None:
    hass = _FakeHass()
    hass.config_entries.async_entries = lambda domain: [
        SimpleNamespace(entry_id="entry", state=ConfigEntryState.LOADED),
        SimpleNamespace(entry_id="other", state=ConfigEntryState.LOADED),
    ]
    register_services(hass)
    unregister_services(hass, "entry")
    assert len(hass.services.handlers) == 5
