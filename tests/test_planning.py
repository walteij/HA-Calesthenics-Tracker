"""Tests for the local A/B workout schedule and next-workout sensor."""

from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorEntityDescription

from custom_components.calisthenics_tracker.calculations import (
    current_program_week,
    next_workout,
)
from custom_components.calisthenics_tracker.models import Workout
from custom_components.calisthenics_tracker.sensor import TrackerSensor


def test_current_program_week_uses_seven_day_blocks() -> None:
    timezone = ZoneInfo("Europe/Amsterdam")
    start_date = datetime(2026, 11, 8).date()
    assert (
        current_program_week(
            start_date, datetime(2026, 11, 8, 23, 59, tzinfo=timezone), timezone
        )
        == 1
    )
    assert (
        current_program_week(
            start_date, datetime(2026, 11, 14, 23, 59, tzinfo=timezone), timezone
        )
        == 1
    )
    assert (
        current_program_week(
            start_date, datetime(2026, 11, 15, 0, 0, tzinfo=timezone), timezone
        )
        == 2
    )
    assert (
        current_program_week(
            start_date, datetime(2026, 11, 7, 23, 0, tzinfo=timezone), timezone
        )
        is None
    )


def test_current_program_week_uses_local_date_across_dst() -> None:
    timezone = ZoneInfo("Europe/Amsterdam")
    assert (
        current_program_week(
            datetime(2026, 3, 22).date(),
            datetime(2026, 3, 29, 22, 30, tzinfo=ZoneInfo("UTC")),
            timezone,
        )
        == 2
    )


def _completed_workout(session_type: str, completed_at: str) -> Workout:
    completed = datetime.fromisoformat(completed_at)
    return Workout(
        workout_id=f"00000000-0000-0000-0000-{len(completed_at):012d}",
        session_type=session_type,
        started_at=completed.replace(hour=9),
        completed_at=completed,
        duration_minutes=30,
        status="completed",
    )


def test_next_workout_uses_wednesday_and_friday_schedule() -> None:
    timezone = ZoneInfo("Europe/Amsterdam")
    assert next_workout((), datetime(2026, 11, 11, 8, tzinfo=timezone), timezone) == (
        "A",
        datetime(2026, 11, 11).date(),
    )
    assert next_workout((), datetime(2026, 11, 13, 8, tzinfo=timezone), timezone) == (
        "B",
        datetime(2026, 11, 13).date(),
    )


def test_sunday_alternates_from_last_completed_sunday() -> None:
    timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime(2026, 11, 15, 8, tzinfo=timezone)
    assert next_workout((), now, timezone) == ("A", now.date())
    assert next_workout(
        (_completed_workout("A", "2026-11-08T10:00:00+01:00"),), now, timezone
    ) == ("B", now.date())
    assert next_workout(
        (_completed_workout("B", "2026-11-08T10:00:00+01:00"),), now, timezone
    ) == ("A", now.date())


def test_completed_training_today_advances_to_the_next_scheduled_day() -> None:
    timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime(2026, 11, 11, 18, tzinfo=timezone)
    assert next_workout(
        (_completed_workout("A", "2026-11-11T17:00:00+01:00"),), now, timezone
    ) == ("B", datetime(2026, 11, 13).date())


def test_schedule_uses_local_date_across_timezone_boundary() -> None:
    timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime(2026, 3, 29, 23, 30, tzinfo=ZoneInfo("UTC"))
    assert next_workout((), now, timezone) == ("A", datetime(2026, 4, 1).date())


def test_next_workout_sensor_exposes_session_and_scheduled_date(
    monkeypatch,
) -> None:
    timezone = ZoneInfo("Europe/Amsterdam")
    now = datetime(2026, 11, 11, 8, tzinfo=timezone)
    monkeypatch.setattr(
        "custom_components.calisthenics_tracker.sensor.dt_util.utcnow",
        lambda: now,
    )
    coordinator = type(
        "Coordinator",
        (),
        {
            "data": type("Data", (), {"workouts": ()})(),
        },
    )()
    sensor = TrackerSensor(
        coordinator,
        "entry",
        SensorEntityDescription(key="next_workout"),
    )
    sensor.hass = type(
        "Hass",
        (),
        {"config": type("Config", (), {"time_zone": "Europe/Amsterdam"})()},
    )()
    assert sensor.native_value == "A"
    assert sensor.extra_state_attributes == {"scheduled_date": now.date().isoformat()}
