"""Typed, validated records and JSON serialization."""

from dataclasses import dataclass, field
from datetime import date, datetime
from math import isfinite
from typing import Any
from uuid import UUID

from homeassistant.util import dt as dt_util

from .const import LEVELS, SESSION_TYPES, STORAGE_VERSION


class InvalidTrackerData(ValueError):
    """Stored data cannot safely be interpreted."""


class InvalidExerciseLog(InvalidTrackerData):
    """An exercise action contains an invalid field."""

    def __init__(self, translation_key: str) -> None:
        self.translation_key = translation_key
        super().__init__(translation_key)


class InvalidBodyMeasurement(InvalidTrackerData):
    """A body-measurement action or stored record contains an invalid field."""

    def __init__(self, translation_key: str) -> None:
        self.translation_key = translation_key
        super().__init__(translation_key)


def aware_datetime(value: str | datetime) -> datetime:
    """Accept only explicit, timezone-aware timestamps and normalize to UTC."""
    parsed = dt_util.parse_datetime(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise InvalidTrackerData("A timezone-aware timestamp is required")
    return dt_util.as_utc(parsed)


def _text(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidTrackerData(f"Invalid {key}")
    return value.strip()


def _integer(value: Any, key: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidTrackerData(f"Invalid {key}")
    return value


def _number(value: Any, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTrackerData(f"Invalid {key}")
    if not _is_finite(value) or value < 0:
        raise InvalidTrackerData(f"Invalid {key}")
    return float(value)


def _is_finite(value: int | float) -> bool:
    try:
        return isfinite(value)
    except OverflowError:
        return False


def _optional_text(value: Any, key: str) -> str | None:
    if value is None:
        return None
    return _text(value, key)


def _optional_repetitions(value: Any, key: str) -> int | None:
    if value is None:
        return None
    return _integer(value, key, 1, 100000)


@dataclass(frozen=True, slots=True)
class ExerciseDefinition:
    """One prescribed exercise from the workbook."""

    exercise_id: str
    name: str
    level: str
    target_sets: int
    unit: str
    session_type: str | None = None
    maximum_sets: int | None = None
    minimum_repetitions: int | None = None
    maximum_repetitions: int | None = None
    tempo: str | None = None
    regression: str | None = None
    progression: str | None = None
    prescription: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExerciseDefinition:
        """Validate an exercise definition from storage."""
        try:
            exercise_id = _text(data["exercise_id"], "exercise_id")
            level = data["level"]
            session_type = data.get("session_type")
            minimum_repetitions = _optional_repetitions(
                data.get("minimum_repetitions"), "minimum_repetitions"
            )
            maximum_repetitions = _optional_repetitions(
                data.get("maximum_repetitions"), "maximum_repetitions"
            )
            maximum_sets = data.get("maximum_sets")
            if maximum_sets is not None:
                maximum_sets = _integer(maximum_sets, "maximum_sets", 1, 50)
            target_sets = _integer(data["target_sets"], "target_sets", 1, 50)
            if (
                level not in LEVELS
                or session_type not in (*SESSION_TYPES, None)
                or (maximum_sets is not None and maximum_sets < target_sets)
                or (
                    minimum_repetitions is not None
                    and maximum_repetitions is not None
                    and maximum_repetitions < minimum_repetitions
                )
            ):
                raise InvalidTrackerData("Invalid exercise prescription")
            return cls(
                exercise_id=exercise_id,
                name=_text(data["name"], "name"),
                level=level,
                target_sets=target_sets,
                unit=_text(data["unit"], "unit"),
                session_type=session_type,
                maximum_sets=maximum_sets,
                minimum_repetitions=minimum_repetitions,
                maximum_repetitions=maximum_repetitions,
                tempo=_optional_text(data.get("tempo"), "tempo"),
                regression=_optional_text(data.get("regression"), "regression"),
                progression=_optional_text(data.get("progression"), "progression"),
                prescription=_optional_text(data.get("prescription"), "prescription"),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise InvalidTrackerData("Invalid exercise definition") from err

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible definition."""
        return {
            "exercise_id": self.exercise_id,
            "name": self.name,
            "level": self.level,
            "session_type": self.session_type,
            "target_sets": self.target_sets,
            "maximum_sets": self.maximum_sets,
            "minimum_repetitions": self.minimum_repetitions,
            "maximum_repetitions": self.maximum_repetitions,
            "unit": self.unit,
            "tempo": self.tempo,
            "regression": self.regression,
            "progression": self.progression,
            "prescription": self.prescription,
        }


@dataclass(frozen=True, slots=True)
class ExerciseLog:
    """One exercise's corrected-in-place set data for a workout."""

    exercise_id: str
    variant: str
    sets: tuple[int | float, ...]
    rir: int
    pain_score: int
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExerciseLog:
        """Validate set measurements and their associated safety scores."""
        try:
            exercise_id = data["exercise_id"]
            if not isinstance(exercise_id, str) or not exercise_id.strip():
                raise InvalidExerciseLog("invalid_exercise")
            variant = data["variant"]
            if not isinstance(variant, str) or not variant.strip():
                raise InvalidExerciseLog("invalid_variant")
            raw_sets = data["sets"]
            if not isinstance(raw_sets, (list, tuple)) or not raw_sets:
                raise InvalidExerciseLog("invalid_sets")
            sets: list[int | float] = []
            for value in raw_sets:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not _is_finite(value)
                    or value <= 0
                ):
                    raise InvalidExerciseLog("invalid_sets")
                sets.append(value)
            rir = data["rir"]
            pain_score = data["pain_score"]
            if type(rir) is not int or not 0 <= rir <= 5:
                raise InvalidExerciseLog("invalid_rir")
            if type(pain_score) is not int or not 0 <= pain_score <= 10:
                raise InvalidExerciseLog("invalid_pain_score")
            notes = data.get("notes", "")
            if not isinstance(notes, str):
                raise InvalidExerciseLog("invalid_exercise_notes")
            return cls(
                exercise_id=exercise_id.strip(),
                variant=variant.strip(),
                sets=tuple(sets),
                rir=rir,
                pain_score=pain_score,
                notes=notes,
            )
        except InvalidExerciseLog:
            raise
        except (KeyError, TypeError, ValueError) as err:
            raise InvalidTrackerData("Invalid exercise log") from err

    def to_dict(self) -> dict[str, Any]:
        """Serialize one log without losing set ordering."""
        return {
            "exercise_id": self.exercise_id,
            "variant": self.variant,
            "sets": list(self.sets),
            "rir": self.rir,
            "pain_score": self.pain_score,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class Profile:
    """Personal configuration, without invented nutritional targets."""

    name: str
    start_date: date
    current_level: str
    goal: str
    target_sessions_per_week: int
    daily_step_target: int
    calorie_deficit_target: float | None = None
    protein_target_per_kg: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Validate both config-flow input and stored profile data."""
        try:
            start_date = date.fromisoformat(data["start_date"])
            level = data["current_level"]
            if level not in LEVELS:
                raise InvalidTrackerData("Invalid current_level")
            return cls(
                name=_text(data["name"], "name"),
                start_date=start_date,
                current_level=level,
                goal=_text(data["goal"], "goal"),
                target_sessions_per_week=_integer(
                    data["target_sessions_per_week"],
                    "target_sessions_per_week",
                    1,
                    7,
                ),
                daily_step_target=_integer(
                    data["daily_step_target"], "daily_step_target", 1, 100000
                ),
                calorie_deficit_target=(
                    _number(data["calorie_deficit_target"], "calorie_deficit_target")
                    if data.get("calorie_deficit_target") is not None
                    else None
                ),
                protein_target_per_kg=(
                    _number(data["protein_target_per_kg"], "protein_target_per_kg")
                    if data.get("protein_target_per_kg") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise InvalidTrackerData("Invalid profile") from err

    def to_dict(self) -> dict[str, Any]:
        """Return the persistent representation."""
        return {
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "current_level": self.current_level,
            "goal": self.goal,
            "target_sessions_per_week": self.target_sessions_per_week,
            "daily_step_target": self.daily_step_target,
            "calorie_deficit_target": self.calorie_deficit_target,
            "protein_target_per_kg": self.protein_target_per_kg,
        }


@dataclass(frozen=True, slots=True)
class Workout:
    """A workout lifecycle with separately logged exercises and sets."""

    workout_id: str
    session_type: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_minutes: float | None = None
    status: str = "active"
    notes: str = ""
    exercises: tuple[ExerciseLog, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workout:
        """Reject inconsistent lifecycle records rather than losing them."""
        try:
            workout_id = str(UUID(data["workout_id"]))
            session_type = data["session_type"]
            status = data["status"]
            started_at = aware_datetime(data["started_at"])
            completed_at = (
                aware_datetime(data["completed_at"])
                if data.get("completed_at") is not None
                else None
            )
            duration = data.get("duration_minutes")
            notes = data.get("notes", "")
            raw_exercises = data.get("exercises", [])
            if (
                session_type not in SESSION_TYPES
                or status not in ("active", "completed", "cancelled")
                or not isinstance(notes, str)
                or not isinstance(raw_exercises, list)
                or any(not isinstance(item, dict) for item in raw_exercises)
            ):
                raise InvalidTrackerData("Invalid workout fields")
            exercises = tuple(ExerciseLog.from_dict(item) for item in raw_exercises)
            if len({item.exercise_id for item in exercises}) != len(exercises):
                raise InvalidTrackerData("Duplicate exercise log")
            if status == "active":
                if completed_at is not None or duration is not None:
                    raise InvalidTrackerData("Active workout has an end")
            else:
                if completed_at is None or completed_at < started_at:
                    raise InvalidTrackerData("Invalid workout end")
                duration = _number(duration, "duration_minutes")
                expected = (completed_at - started_at).total_seconds() / 60
                if abs(duration - expected) > 0.000001:
                    raise InvalidTrackerData("Inconsistent workout duration")
            return cls(
                workout_id,
                session_type,
                started_at,
                completed_at,
                duration,
                status,
                notes,
                exercises,
            )
        except (KeyError, TypeError, ValueError, AttributeError) as err:
            raise InvalidTrackerData("Invalid workout") from err

    def to_dict(self) -> dict[str, Any]:
        """Serialize datetimes without dropping their timezone."""
        return {
            "workout_id": self.workout_id,
            "session_type": self.session_type,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at is not None else None
            ),
            "duration_minutes": self.duration_minutes,
            "status": self.status,
            "notes": self.notes,
            "exercises": [exercise.to_dict() for exercise in self.exercises],
        }


@dataclass(frozen=True, slots=True)
class BodyMeasurement:
    """One local body and wellbeing measurement."""

    measurement_id: str
    measured_at: datetime
    weight_kg: float | None = None
    waist_cm: float | None = None
    resting_heart_rate: int | None = None
    steps: int | None = None
    sleep_hours: float | None = None
    calorie_intake: float | None = None
    protein_grams: float | None = None
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BodyMeasurement:
        """Validate and normalize one stored measurement."""
        try:
            measurement_id = str(UUID(data["measurement_id"]))
            measured_at = aware_datetime(data["measured_at"])
            weight_kg = _optional_measurement_number(
                data.get("weight_kg"),
                "invalid_weight",
                minimum=0,
                maximum=500,
                exclusive=True,
            )
            waist_cm = _optional_measurement_number(
                data.get("waist_cm"),
                "invalid_waist",
                minimum=0,
                maximum=300,
                exclusive=True,
            )
            resting_heart_rate = _optional_measurement_integer(
                data.get("resting_heart_rate"), "invalid_resting_heart_rate", 1, 300
            )
            steps = _optional_measurement_integer(data.get("steps"), "invalid_steps", 0)
            sleep_hours = _optional_measurement_number(
                data.get("sleep_hours"), "invalid_sleep_hours", minimum=0, maximum=24
            )
            calorie_intake = _optional_measurement_number(
                data.get("calorie_intake"), "invalid_calorie_intake", minimum=0
            )
            protein_grams = _optional_measurement_number(
                data.get("protein_grams"), "invalid_protein_grams", minimum=0
            )
            notes = data.get("notes", "")
            if not isinstance(notes, str):
                raise InvalidBodyMeasurement("invalid_measurement_notes")
            if all(
                value is None
                for value in (
                    weight_kg,
                    waist_cm,
                    resting_heart_rate,
                    steps,
                    sleep_hours,
                    calorie_intake,
                    protein_grams,
                )
            ):
                raise InvalidBodyMeasurement("empty_measurement")
            return cls(
                measurement_id=measurement_id,
                measured_at=measured_at,
                weight_kg=weight_kg,
                waist_cm=waist_cm,
                resting_heart_rate=resting_heart_rate,
                steps=steps,
                sleep_hours=sleep_hours,
                calorie_intake=calorie_intake,
                protein_grams=protein_grams,
                notes=notes,
            )
        except InvalidBodyMeasurement:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as err:
            raise InvalidBodyMeasurement("invalid_measurement") from err

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible measurement record."""
        return {
            "measurement_id": self.measurement_id,
            "measured_at": self.measured_at.isoformat(),
            "weight_kg": self.weight_kg,
            "waist_cm": self.waist_cm,
            "resting_heart_rate": self.resting_heart_rate,
            "steps": self.steps,
            "sleep_hours": self.sleep_hours,
            "calorie_intake": self.calorie_intake,
            "protein_grams": self.protein_grams,
            "notes": self.notes,
        }


def _optional_measurement_number(
    value: Any,
    key: str,
    *,
    minimum: float,
    maximum: float | None = None,
    exclusive: bool = False,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidBodyMeasurement(key)
    if not _is_finite(value):
        raise InvalidBodyMeasurement(key)
    if value <= minimum if exclusive else value < minimum:
        raise InvalidBodyMeasurement(key)
    if maximum is not None and value > maximum:
        raise InvalidBodyMeasurement(key)
    return float(value)


def _optional_measurement_integer(
    value: Any, key: str, minimum: int, maximum: int | None = None
) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < minimum:
        raise InvalidBodyMeasurement(key)
    if maximum is not None and value > maximum:
        raise InvalidBodyMeasurement(key)
    return value


@dataclass(frozen=True, slots=True)
class TrackerData:
    """Versioned profile, exercise catalog, and workout history."""

    profile: Profile
    workouts: tuple[Workout, ...] = field(default_factory=tuple)
    exercise_definitions: tuple[ExerciseDefinition, ...] = field(default_factory=tuple)
    body_measurements: tuple[BodyMeasurement, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: Any) -> TrackerData:
        """Validate the full payload before exposing any records."""
        if not isinstance(data, dict):
            raise InvalidTrackerData("Storage must be an object")
        if (
            type(data.get("schema_version")) is not int
            or data["schema_version"] != STORAGE_VERSION
        ):
            raise InvalidTrackerData("Unsupported schema version")
        if not isinstance(data.get("profile"), dict):
            raise InvalidTrackerData("Missing profile")
        raw_definitions = data.get("exercise_definitions")
        if not isinstance(raw_definitions, list) or any(
            not isinstance(item, dict) for item in raw_definitions
        ):
            raise InvalidTrackerData("Invalid exercise catalog")
        definitions = tuple(
            ExerciseDefinition.from_dict(item) for item in raw_definitions
        )
        if len({item.exercise_id for item in definitions}) != len(definitions):
            raise InvalidTrackerData("Duplicate exercise definition")
        records = data.get("workouts")
        if not isinstance(records, list) or any(
            not isinstance(record, dict) for record in records
        ):
            raise InvalidTrackerData("Invalid workout list")
        workouts = tuple(Workout.from_dict(record) for record in records)
        if len({workout.workout_id for workout in workouts}) != len(workouts):
            raise InvalidTrackerData("Duplicate workout ID")
        if sum(workout.status == "active" for workout in workouts) > 1:
            raise InvalidTrackerData("Multiple active workouts")
        known_exercises = {item.exercise_id for item in definitions}
        if any(
            log.exercise_id not in known_exercises
            for workout in workouts
            for log in workout.exercises
        ):
            raise InvalidTrackerData("Workout references an unknown exercise")
        raw_measurements = data.get("body_measurements", [])
        if not isinstance(raw_measurements, list) or any(
            not isinstance(item, dict) for item in raw_measurements
        ):
            raise InvalidTrackerData("Invalid body-measurement list")
        measurements = tuple(
            BodyMeasurement.from_dict(item) for item in raw_measurements
        )
        if len({item.measurement_id for item in measurements}) != len(measurements):
            raise InvalidTrackerData("Duplicate body-measurement ID")
        return cls(
            Profile.from_dict(data["profile"]), workouts, definitions, measurements
        )

    def to_dict(self) -> dict[str, Any]:
        """Return schema-versioned storage data."""
        return {
            "schema_version": STORAGE_VERSION,
            "profile": self.profile.to_dict(),
            "exercise_definitions": [
                definition.to_dict() for definition in self.exercise_definitions
            ],
            "workouts": [workout.to_dict() for workout in self.workouts],
            "body_measurements": [
                measurement.to_dict() for measurement in self.body_measurements
            ],
        }
