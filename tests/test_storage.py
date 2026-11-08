"""Storage initialization, save/load, and migration behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.calisthenics_tracker import async_remove_entry
from custom_components.calisthenics_tracker.coordinator import TrackerCoordinator
from custom_components.calisthenics_tracker.models import (
    BodyMeasurement,
    ExerciseLog,
    InvalidTrackerData,
    Profile,
    TrackerData,
    Workout,
)
from custom_components.calisthenics_tracker.storage import (
    TrackerStorage,
    migrate_payload,
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
class _FakeStore:
    path: str
    loaded: Any = None
    saved: Any = None

    async def async_load(self) -> Any:
        return self.loaded

    async def async_save(self, data: Any) -> None:
        self.saved = data
        self.loaded = data


class _FakeHass:
    async def async_add_executor_job(self, func, *args):
        return func(*args)


def _make_storage(store: _FakeStore) -> TrackerStorage:
    storage = object.__new__(TrackerStorage)
    storage._hass = _FakeHass()
    storage._store = store
    return storage


@pytest.mark.asyncio
async def test_storage_initializes_missing_payload() -> None:
    with TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "tracker.json")
        storage = _make_storage(_FakeStore(path=path, loaded=None))
        loaded = await storage.async_load(_profile())
        assert loaded.profile.name == "Walter"
        assert loaded.workouts == ()


@pytest.mark.asyncio
async def test_storage_load_and_save_round_trip() -> None:
    with TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "tracker.json")
        store = _FakeStore(path=path, loaded=None)
        storage = _make_storage(store)
        initial = await storage.async_load(_profile())
        assert len(initial.exercise_definitions) == 22
        await storage.async_save(initial)
        loaded = await storage.async_load(_profile())
        assert loaded.to_dict()["profile"]["name"] == "Walter"
        assert len(loaded.exercise_definitions) == 22


@pytest.mark.asyncio
async def test_storage_round_trips_exercise_logs() -> None:
    with TemporaryDirectory() as tmp:
        storage = _make_storage(_FakeStore(path=str(Path(tmp) / "tracker.json")))
        initial = await storage.async_load(_profile())
        exercise = ExerciseLog(
            exercise_id="beginner_push_up",
            variant="Incline push-up",
            sets=(10, 9, 8),
            rir=2,
            pain_score=0,
        )
        workout = Workout(
            workout_id="158f729e-67d1-4d5e-bec9-c4d6ea84a5f9",
            session_type="A",
            started_at=dt_util.parse_datetime("2026-11-08T08:00:00+00:00"),
            completed_at=dt_util.parse_datetime("2026-11-08T08:30:00+00:00"),
            duration_minutes=30.0,
            status="completed",
            exercises=(exercise,),
        )
        assert workout.completed_at is not None
        data = TrackerData(initial.profile, (workout,), initial.exercise_definitions)
        await storage.async_save(data)
        loaded = await storage.async_load(_profile())
        assert loaded.workouts[0].exercises[0].sets == (10, 9, 8)


def test_storage_migrates_version_zero_payload() -> None:
    migrated = migrate_payload(
        0,
        {
            "schema_version": 0,
            "profile": _profile().to_dict(),
            "workouts": [],
        },
    )
    data = TrackerData.from_dict(migrated)
    assert data.profile.current_level == "beginner"
    assert len(data.exercise_definitions) == 22


def test_storage_migrates_phase_one_version() -> None:
    previous = TrackerData(_profile()).to_dict()
    previous["schema_version"] = 1
    previous["workouts"] = [
        {
            "workout_id": "158f729e-67d1-4d5e-bec9-c4d6ea84a5f9",
            "session_type": "B",
            "started_at": "2026-11-08T08:00:00+00:00",
            "completed_at": None,
            "duration_minutes": None,
            "status": "active",
            "notes": "",
            "exercises": [],
        }
    ]
    migrated = migrate_payload(1, previous)
    data = TrackerData.from_dict(migrated)
    assert data.profile.name == "Walter"
    assert len(data.exercise_definitions) == 22
    assert data.workouts[0].status == "active"


def test_storage_migrates_phase_two_version() -> None:
    previous = TrackerData(_profile()).to_dict()
    previous["schema_version"] = 2
    migrated = migrate_payload(2, previous)
    data = TrackerData.from_dict(migrated)
    assert data.profile.name == "Walter"
    assert data.body_measurements == ()


@pytest.mark.asyncio
async def test_storage_rejects_existing_corrupt_payload() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "tracker.json"
        path.write_text("{corrupt}", encoding="utf-8")
        storage = _make_storage(_FakeStore(path=str(path), loaded=None))
        with pytest.raises(InvalidTrackerData):
            await storage.async_load(_profile())


@pytest.mark.asyncio
async def test_storage_round_trips_body_measurements() -> None:
    with TemporaryDirectory() as tmp:
        storage = _make_storage(_FakeStore(path=str(Path(tmp) / "tracker.json")))
        initial = await storage.async_load(_profile())
        measurement = BodyMeasurement.from_dict(
            {
                "measurement_id": "476a686e-50db-4256-9aa4-aeac7bb5cbb0",
                "measured_at": "2026-11-08T07:30:00+01:00",
                "weight_kg": 79.5,
                "waist_cm": 90,
                "resting_heart_rate": 55,
                "steps": 8000,
                "sleep_hours": 7.5,
                "calorie_intake": 2200,
                "protein_grams": 140,
                "notes": "morning",
            }
        )
        await storage.async_save(
            TrackerData(
                initial.profile,
                initial.workouts,
                initial.exercise_definitions,
                (measurement,),
            )
        )
        loaded = await storage.async_load(_profile())
        assert loaded.body_measurements == (measurement,)


@pytest.mark.asyncio
async def test_real_store_restores_active_workout_and_measurement_after_restart(
    tmp_path: Path,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        storage = TrackerStorage(hass, "restart-test")
        initial = await storage.async_load(_profile())
        coordinator = TrackerCoordinator(hass, storage, initial)
        started = await coordinator.async_start_workout(
            "A", "2026-11-08T08:00:00+00:00"
        )
        await coordinator.async_log_exercise(
            "beginner_push_up",
            "Strict push-up",
            [10, 9, 8],
            rir=2,
            pain_score=0,
        )
        measurement = await coordinator.async_add_body_measurement(
            measured_at="2026-11-08T07:30:00+00:00",
            weight_kg=79.5,
            steps=8000,
        )
        await hass.async_block_till_done()

        restarted_storage = TrackerStorage(hass, "restart-test")
        restored = await restarted_storage.async_load(_profile())

        assert restored.profile.name == "Walter"
        assert len(restored.exercise_definitions) == 22
        assert len(restored.workouts) == 1
        assert restored.workouts[0].workout_id == started.workout_id
        assert restored.workouts[0].status == "active"
        assert restored.workouts[0].exercises[0].sets == (10, 9, 8)
        assert restored.body_measurements == (measurement,)
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_removing_config_entry_deletes_private_tracker_storage(
    tmp_path: Path,
) -> None:
    hass = HomeAssistant(str(tmp_path))
    try:
        storage = TrackerStorage(hass, "remove-test")
        initial = await storage.async_load(_profile())
        coordinator = TrackerCoordinator(hass, storage, initial)
        await coordinator.async_start_workout("A", "2026-11-08T08:00:00+00:00")
        await hass.async_block_till_done()

        await async_remove_entry(hass, SimpleNamespace(entry_id="remove-test"))

        restored = await TrackerStorage(hass, "remove-test").async_load(_profile())
        assert restored.workouts == ()
    finally:
        await hass.async_stop()
