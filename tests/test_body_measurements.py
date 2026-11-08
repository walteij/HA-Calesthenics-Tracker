"""Body-measurement calculations and action persistence."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.calisthenics_tracker.calculations import (
    average_measurement_over_7_days,
    latest_measurement_value,
    weight_change_since_start,
)
from custom_components.calisthenics_tracker.coordinator import TrackerCoordinator
from custom_components.calisthenics_tracker.models import (
    BodyMeasurement,
    Profile,
    TrackerData,
)


def _measurement(
    measurement_id: str,
    measured_at: str,
    **values: int | float | None,
) -> BodyMeasurement:
    return BodyMeasurement.from_dict(
        {
            "measurement_id": measurement_id,
            "measured_at": measured_at,
            **values,
        }
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


class _MemoryStorage:
    def __init__(self, data: TrackerData) -> None:
        self.data = data

    async def async_save(self, data: TrackerData) -> None:
        self.data = data


class _FakeHass:
    config = SimpleNamespace(time_zone="Europe/Amsterdam")


def test_7_day_averages_use_measured_local_days_and_ignore_gaps() -> None:
    measurements = (
        _measurement(
            "01f09324-79e2-46a1-b5e2-500b258704ad",
            "2026-03-24T08:00:00+01:00",
            weight_kg=80,
            steps=6000,
            sleep_hours=6,
        ),
        _measurement(
            "75d87074-621e-4534-b95f-36e145bfab09",
            "2026-03-24T20:00:00+02:00",
            weight_kg=79,
            steps=8000,
            sleep_hours=8,
        ),
        _measurement(
            "afbe44c4-bae5-4db4-b0f6-379aa875f087",
            "2026-03-30T08:00:00+02:00",
            weight_kg=78,
            steps=10000,
            sleep_hours=7,
        ),
        _measurement(
            "75d0b934-c5fa-47b6-9aa9-5be48d4eced9",
            "2026-03-23T23:59:00+02:00",
            weight_kg=70,
            steps=2000,
            sleep_hours=5,
        ),
        _measurement(
            "8838ee31-8050-4b6a-9c4a-9be7f3b4e427",
            "2026-03-30T11:00:00+02:00",
            weight_kg=77,
            steps=11000,
            sleep_hours=9,
        ),
    )
    now = datetime(2026, 3, 30, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    timezone = ZoneInfo("Europe/Amsterdam")

    assert (
        average_measurement_over_7_days(measurements, "weight_kg", now, timezone)
        == 78.0
    )
    assert average_measurement_over_7_days(measurements, "steps", now, timezone) == 9500
    assert (
        average_measurement_over_7_days(measurements, "sleep_hours", now, timezone)
        == 8.5
    )


def test_7_day_average_is_unavailable_without_a_recent_measurement() -> None:
    measurements = (
        _measurement(
            "64d83372-d16d-4893-9a9d-ebde37d63a23",
            "2026-11-01T08:00:00+01:00",
            weight_kg=80,
        ),
    )
    now = datetime(2026, 11, 8, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    assert (
        average_measurement_over_7_days(
            measurements, "weight_kg", now, ZoneInfo("Europe/Amsterdam")
        )
        is None
    )
    assert (
        average_measurement_over_7_days((), "weight_kg", now, ZoneInfo("UTC")) is None
    )


def test_latest_weight_and_change_since_start() -> None:
    measurements = (
        _measurement(
            "87d4e14b-bb43-4fc6-9b85-c168bdb781fb",
            "2026-11-01T08:00:00+01:00",
            weight_kg=82.5,
            waist_cm=95,
        ),
        _measurement(
            "c1257744-c2b7-448b-b65b-13f33311387f",
            "2026-11-08T08:00:00+01:00",
            weight_kg=80,
            steps=9000,
        ),
    )
    assert latest_measurement_value(measurements, "weight_kg") == 80
    assert latest_measurement_value(measurements, "waist_cm") == 95
    assert weight_change_since_start(measurements) == -2.5
    assert weight_change_since_start(()) is None


@pytest.mark.asyncio
async def test_add_body_measurement_persists_and_notifies() -> None:
    initial = TrackerData(_profile())
    storage = _MemoryStorage(initial)
    coordinator = TrackerCoordinator(_FakeHass(), storage, initial)
    notifications: list[bool] = []
    coordinator.async_add_listener(lambda: notifications.append(True))

    measurement = await coordinator.async_add_body_measurement(
        measured_at=(dt_util.utcnow() - timedelta(minutes=1)).isoformat(),
        weight_kg=79.5,
        waist_cm=90,
        resting_heart_rate=55,
        steps=9000,
        sleep_hours=7.5,
        calorie_intake=2200,
        protein_grams=140,
    )

    assert measurement.measurement_id
    assert measurement.weight_kg == 79.5
    assert storage.data.body_measurements == (measurement,)
    assert notifications == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "translation_key"),
    [
        ("weight_kg", 0, "invalid_weight"),
        ("weight_kg", 501, "invalid_weight"),
        ("waist_cm", 301, "invalid_waist"),
        ("resting_heart_rate", 0, "invalid_resting_heart_rate"),
        ("steps", -1, "invalid_steps"),
        ("steps", 1.5, "invalid_steps"),
        ("sleep_hours", 24.1, "invalid_sleep_hours"),
        ("calorie_intake", float("inf"), "invalid_calorie_intake"),
        ("protein_grams", True, "invalid_protein_grams"),
    ],
)
async def test_add_body_measurement_rejects_invalid_values(
    field: str, value: int | float, translation_key: str
) -> None:
    initial = TrackerData(_profile())
    coordinator = TrackerCoordinator(_FakeHass(), _MemoryStorage(initial), initial)
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_add_body_measurement(**{field: value})
    assert err.value.translation_key == translation_key


@pytest.mark.asyncio
async def test_add_body_measurement_requires_a_value_and_rejects_future_time() -> None:
    initial = TrackerData(_profile())
    coordinator = TrackerCoordinator(_FakeHass(), _MemoryStorage(initial), initial)
    with pytest.raises(ServiceValidationError) as empty_error:
        await coordinator.async_add_body_measurement(notes="only a note")
    assert empty_error.value.translation_key == "empty_measurement"
    with pytest.raises(ServiceValidationError) as future_error:
        await coordinator.async_add_body_measurement(
            measured_at=(dt_util.utcnow() + timedelta(days=1)).isoformat(),
            weight_kg=80,
        )
    assert future_error.value.translation_key == "future_timestamp"


def test_body_measurement_round_trip_is_timezone_aware() -> None:
    record = _measurement(
        "5ac44b74-ad9f-45cc-9fee-86614df274c9",
        "2026-11-08T07:30:00+01:00",
        weight_kg=79.2,
        steps=8000,
    )
    restored = BodyMeasurement.from_dict(record.to_dict())
    assert restored == record
    assert restored.measured_at.utcoffset() == timedelta(0)
