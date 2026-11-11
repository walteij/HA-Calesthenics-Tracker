"""Weekly totals and sensor-level state derivation."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.util import dt as dt_util

from custom_components.calisthenics_tracker.calculations import weekly_totals
from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES
from custom_components.calisthenics_tracker.models import (
    BodyMeasurement,
    Profile,
    TrackerData,
    Workout,
)
from custom_components.calisthenics_tracker.sensor import (
    SENSORS,
    ExerciseProgressSensor,
    TrackerSensor,
)


def _workout(workout_id: str, completed_at: str, minutes: float) -> Workout:
    completed = dt_util.parse_datetime(completed_at)
    assert completed is not None
    started = completed - timedelta(minutes=minutes)
    return Workout.from_dict(
        {
            "workout_id": workout_id,
            "session_type": "A",
            "started_at": started.isoformat(),
            "completed_at": completed_at,
            "duration_minutes": minutes,
            "status": "completed",
            "notes": "",
            "exercises": [],
        }
    )


def test_weekly_totals_sunday_and_monday_boundaries() -> None:
    tz = ZoneInfo("Europe/Amsterdam")
    workouts = (
        _workout(
            "2f2a8d47-59b4-46dd-8e45-74458239a320", "2026-11-08T20:00:00+01:00", 30
        ),
        _workout(
            "6dc8cde6-e596-476d-a0a4-9f6cf888f452", "2026-11-09T20:00:00+01:00", 40
        ),
    )
    now = datetime(2026, 11, 9, 21, 0, tzinfo=tz).astimezone(ZoneInfo("UTC"))
    sessions, minutes = weekly_totals(workouts, now, tz)
    assert sessions == 1
    assert minutes == 40.0


def test_weekly_totals_handles_dst_local_dates() -> None:
    tz = ZoneInfo("Europe/Amsterdam")
    workouts = (
        _workout(
            "dd4ea5c8-f6a1-4565-8d9b-e6d2ab49b417", "2026-03-30T01:30:00+02:00", 35
        ),
        _workout(
            "5e72929e-4120-4362-8da2-7a6123cc7b7f", "2026-03-31T01:30:00+02:00", 25
        ),
    )
    sessions, minutes = weekly_totals(
        workouts, datetime(2026, 3, 31, 9, 0, tzinfo=ZoneInfo("UTC")), tz
    )
    assert sessions == 2
    assert minutes == 60.0


def test_active_workout_sensor_state_from_coordinator() -> None:
    active = Workout.from_dict(
        {
            "workout_id": "a68cb6c9-5921-453f-b8dc-5d642f94dbca",
            "session_type": "A",
            "started_at": "2026-11-09T10:00:00+01:00",
            "completed_at": None,
            "duration_minutes": None,
            "status": "active",
            "notes": "",
            "exercises": [],
        }
    )
    coordinator = type(
        "Coordinator",
        (),
        {
            "data": TrackerData(
                profile=type("P", (), {"name": "x"})(), workouts=(active,)
            ),
            "active_workout": active,
        },
    )()
    sensor = TrackerSensor(
        coordinator, "entry", SensorEntityDescription(key="active_workout")
    )
    assert sensor.native_value == "A"


def test_current_level_and_program_week_sensors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime(2026, 11, 15, 8, tzinfo=timezone)
    profile = Profile(
        name="Test",
        start_date=datetime(2026, 11, 8).date(),
        current_level="beginner",
        goal="Strength",
        target_sessions_per_week=3,
        daily_step_target=8000,
    )
    coordinator = type(
        "Coordinator",
        (),
        {
            "data": TrackerData(profile=profile),
            "active_workout": None,
        },
    )()
    monkeypatch.setattr(
        "custom_components.calisthenics_tracker.sensor.dt_util.utcnow",
        lambda: now.astimezone(ZoneInfo("UTC")),
    )
    hass = type(
        "Hass",
        (),
        {"config": type("Config", (), {"time_zone": "Europe/Amsterdam"})()},
    )()
    values = {
        key: TrackerSensor(
            coordinator,
            "entry",
            SensorEntityDescription(key=key),
        )
        for key in ("current_level", "current_week")
    }
    for sensor in values.values():
        sensor.hass = hass
    assert {key: sensor.native_value for key, sensor in values.items()} == {
        "current_level": "beginner",
        "current_week": 2,
    }


def test_body_measurement_sensors_use_coordinator_records() -> None:
    timestamp = dt_util.utcnow()
    measurement = BodyMeasurement.from_dict(
        {
            "measurement_id": "74f74083-5ad0-49f6-b948-0b1797ef630e",
            "measured_at": timestamp.isoformat(),
            "weight_kg": 79.5,
            "waist_cm": 90,
            "steps": 8000,
            "sleep_hours": 7,
        }
    )
    coordinator = type(
        "Coordinator",
        (),
        {
            "data": TrackerData(
                profile=type("P", (), {"name": "x"})(),
                body_measurements=(measurement,),
            ),
            "active_workout": None,
        },
    )()
    values = {}
    for description in SENSORS:
        if description.key in {
            "latest_weight",
            "latest_waist",
            "weight_7_day_average",
            "average_daily_steps_7_days",
            "average_sleep_7_days",
        }:
            sensor = TrackerSensor(coordinator, "entry", description)
            sensor.hass = type(
                "Hass",
                (),
                {"config": type("Config", (), {"time_zone": "Europe/Amsterdam"})()},
            )()
            values[description.key] = sensor.native_value
    assert values == {
        "latest_weight": 79.5,
        "weight_7_day_average": 79.5,
        "latest_waist": 90,
        "average_daily_steps_7_days": 8000,
        "average_sleep_7_days": 7,
    }


def test_graduation_and_per_exercise_progress_sensors_expose_bounded_state() -> None:
    workouts = tuple(
        Workout.from_dict(
            {
                "workout_id": f"00000000-0000-0000-0000-{index + 1:012d}",
                "session_type": "A",
                "started_at": f"2026-11-0{index + 1}T09:30:00+00:00",
                "completed_at": f"2026-11-0{index + 1}T10:00:00+00:00",
                "duration_minutes": 30,
                "status": "completed",
                "notes": "",
                "exercises": [
                    {
                        "exercise_id": "beginner_push_up",
                        "variant": "Strict push-up",
                        "sets": [10, 10, 10],
                        "rir": 2,
                        "pain_score": 0,
                    }
                ],
            }
        )
        for index in range(1, 4)
    )
    definition = next(
        item for item in WORKBOOK_EXERCISES if item.exercise_id == "beginner_push_up"
    )
    coordinator = type(
        "Coordinator",
        (),
        {
            "data": TrackerData(
                profile=type("P", (), {"name": "x"})(),
                workouts=workouts,
                exercise_definitions=(definition,),
            ),
            "active_workout": None,
        },
    )()
    graduation = next(
        item for item in SENSORS if item.key == "beginner_graduation_readiness"
    )
    graduation_sensor = TrackerSensor(coordinator, "entry", graduation)
    assert graduation_sensor.native_value == "not_ready"
    assert graduation_sensor.extra_state_attributes == {
        "push_ups_reps": 10,
        "push_ups_target": 15,
        "dead_hang_pull_ups_reps": None,
        "dead_hang_pull_ups_target": 5,
        "strict_full_depth_squats_reps": None,
        "strict_full_depth_squats_target": 20,
    }

    progress_sensor = ExerciseProgressSensor(coordinator, "entry", definition)
    assert progress_sensor.native_value == "plateau"
    assert len(progress_sensor.extra_state_attributes["recent_sessions"]) == 3
    assert progress_sensor.extra_state_attributes["tutorial_url"] == (
        "https://www.youtube.com/watch?v=IODxDxX7oi4"
    )
