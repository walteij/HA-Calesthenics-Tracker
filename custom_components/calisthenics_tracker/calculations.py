"""Pure calculations based on aware timestamps and a supplied local timezone."""

from datetime import date, datetime, timedelta, tzinfo

from .models import BodyMeasurement, Workout


def weekly_totals(
    workouts: tuple[Workout, ...], now: datetime, timezone: tzinfo
) -> tuple[int, float]:
    """Count completed workouts by local completion date, Monday through Sunday."""
    today = now.astimezone(timezone).date()
    monday = today - timedelta(days=today.weekday())
    next_monday = monday + timedelta(days=7)
    completed = [
        workout
        for workout in workouts
        if workout.status == "completed"
        and workout.completed_at is not None
        and monday <= workout.completed_at.astimezone(timezone).date() < next_monday
        and workout.completed_at <= now
    ]
    return len(completed), round(
        sum(workout.duration_minutes or 0 for workout in completed), 2
    )


def current_program_week(
    start_date: date, now: datetime, timezone: tzinfo
) -> int | None:
    """Return the one-based seven-day training week for the local calendar date."""
    days_since_start = (now.astimezone(timezone).date() - start_date).days
    if days_since_start < 0:
        return None
    return days_since_start // 7 + 1


def next_workout(
    workouts: tuple[Workout, ...], now: datetime, timezone: tzinfo
) -> tuple[str, date]:
    """Return the next scheduled A/B session in the local calendar."""
    local_today = now.astimezone(timezone).date()
    completed = tuple(
        workout
        for workout in workouts
        if workout.status == "completed"
        and workout.completed_at is not None
        and workout.completed_at <= now
    )
    completed_days = {
        workout.completed_at.astimezone(timezone).date()
        for workout in completed
        if workout.completed_at is not None
    }

    for offset in range(8):
        scheduled_date = local_today + timedelta(days=offset)
        weekday = scheduled_date.weekday()
        if weekday not in (2, 4, 6) or scheduled_date in completed_days:
            continue
        if weekday == 2:
            return "A", scheduled_date
        if weekday == 4:
            return "B", scheduled_date

        previous_sundays = [
            workout
            for workout in completed
            if workout.completed_at is not None
            and workout.completed_at.astimezone(timezone).date() < scheduled_date
            and workout.completed_at.astimezone(timezone).weekday() == 6
        ]
        latest_sunday = max(
            previous_sundays,
            key=lambda workout: workout.completed_at or now,
            default=None,
        )
        return (
            ("B" if latest_sunday.session_type == "A" else "A")
            if latest_sunday is not None
            else "A",
            scheduled_date,
        )

    raise RuntimeError("No workout day found within the next week")


def _daily_latest_values(
    measurements: tuple[BodyMeasurement, ...],
    field: str,
    now: datetime,
    timezone: tzinfo,
) -> dict[date, float]:
    """Select the latest recorded value for each measured local calendar day."""
    today = now.astimezone(timezone).date()
    first_day = today - timedelta(days=6)
    latest: dict[date, tuple[datetime, float]] = {}
    for measurement in measurements:
        value = getattr(measurement, field)
        if value is None or measurement.measured_at > now:
            continue
        local_timestamp = measurement.measured_at.astimezone(timezone)
        local_day = local_timestamp.date()
        if not first_day <= local_day <= today:
            continue
        current = latest.get(local_day)
        if current is None or measurement.measured_at > current[0]:
            latest[local_day] = (measurement.measured_at, float(value))
    return {day: record[1] for day, record in latest.items()}


def latest_measurement_value(
    measurements: tuple[BodyMeasurement, ...], field: str
) -> float | None:
    """Return the most recent non-empty value for one measurement field."""
    matching = [
        measurement
        for measurement in measurements
        if getattr(measurement, field) is not None
    ]
    if not matching:
        return None
    latest = max(matching, key=lambda measurement: measurement.measured_at)
    return float(getattr(latest, field))


def average_measurement_over_7_days(
    measurements: tuple[BodyMeasurement, ...],
    field: str,
    now: datetime,
    timezone: tzinfo,
) -> float | None:
    """Average one latest reading per measured local day in the trailing week."""
    daily_values = _daily_latest_values(measurements, field, now, timezone)
    if not daily_values:
        return None
    return round(sum(daily_values.values()) / len(daily_values), 2)


def weight_change_since_start(
    measurements: tuple[BodyMeasurement, ...],
) -> float | None:
    """Return latest recorded weight minus the first recorded weight."""
    weights = [
        measurement for measurement in measurements if measurement.weight_kg is not None
    ]
    if not weights:
        return None
    first = min(weights, key=lambda measurement: measurement.measured_at)
    latest = max(weights, key=lambda measurement: measurement.measured_at)
    first_weight = first.weight_kg
    latest_weight = latest.weight_kg
    assert first_weight is not None and latest_weight is not None
    return round(latest_weight - first_weight, 2)
