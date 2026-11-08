"""Local, push-only state management; no polling coordinator is needed."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SESSION_TYPES
from .models import (
    BodyMeasurement,
    ExerciseLog,
    InvalidBodyMeasurement,
    InvalidExerciseLog,
    InvalidTrackerData,
    TrackerData,
    Workout,
    aware_datetime,
)
from .storage import TrackerStorage

LOGGER = logging.getLogger(__name__)


class TrackerCoordinator:
    """Serialize mutations and publish only successfully persisted state."""

    def __init__(
        self, hass: HomeAssistant, storage: TrackerStorage, data: TrackerData
    ) -> None:
        self.hass = hass
        self.storage = storage
        self.data = data
        self._lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()
        self._closed = False
        self._remove_calendar_listener: Callable[[], None] | None = None

    @property
    def active_workout(self) -> Workout | None:
        """Return the one active workout, if any."""
        return next(
            (workout for workout in self.data.workouts if workout.status == "active"),
            None,
        )

    @callback
    def async_start(self) -> None:
        """Refresh calendar-dependent sensors at local midnight."""
        self._remove_calendar_listener = async_track_time_change(
            self.hass, self._calendar_changed, hour=0, minute=0, second=0
        )

    @callback
    def _calendar_changed(self, now: datetime) -> None:
        self._notify()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity and return its unload callback."""
        self._listeners.add(listener)

        @callback
        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    def _error(self, key: str) -> ServiceValidationError:
        return ServiceValidationError(translation_domain=DOMAIN, translation_key=key)

    def _timestamp(self, value: str | datetime | None) -> datetime:
        try:
            return aware_datetime(value) if value is not None else dt_util.utcnow()
        except InvalidTrackerData as err:
            raise self._error("invalid_timestamp") from err

    async def _commit(self, candidate: TrackerData) -> None:
        try:
            await self.storage.async_save(candidate)
        except OSError as err:
            raise self._error("storage_failed") from err
        self.data = candidate
        self._notify()

    async def async_start_workout(
        self, session_type: str, started_at: str | datetime | None = None
    ) -> Workout:
        """Persist a new active workout before notifying subscribers."""
        async with self._lock:
            if self._closed:
                raise self._error("not_loaded")
            if self.active_workout is not None:
                raise self._error("already_active")
            if session_type not in SESSION_TYPES:
                raise self._error("invalid_session_type")
            timestamp = self._timestamp(started_at)
            if timestamp > dt_util.utcnow():
                raise self._error("future_timestamp")
            workout = Workout(str(uuid4()), session_type, timestamp)
            await self._commit(
                replace(self.data, workouts=(*self.data.workouts, workout))
            )
            return workout

    async def async_complete_workout(
        self, completed_at: str | datetime | None = None, notes: str = ""
    ) -> Workout:
        """Complete an active workout, calculating elapsed UTC minutes."""
        async with self._lock:
            if self._closed:
                raise self._error("not_loaded")
            active = self.active_workout
            if active is None:
                raise self._error("no_active")
            timestamp = self._timestamp(completed_at)
            if timestamp < active.started_at:
                raise self._error("end_before_start")
            if timestamp > dt_util.utcnow():
                raise self._error("future_timestamp")
            if not isinstance(notes, str):
                raise self._error("invalid_notes")
            completed = replace(
                active,
                completed_at=timestamp,
                duration_minutes=(timestamp - active.started_at).total_seconds() / 60,
                status="completed",
                notes=notes,
            )
            await self._commit(
                replace(
                    self.data,
                    workouts=tuple(
                        completed if item.workout_id == active.workout_id else item
                        for item in self.data.workouts
                    ),
                )
            )
            return completed

    async def async_cancel_workout(self) -> Workout:
        """Persist the active workout as cancelled without counting it as complete."""
        async with self._lock:
            if self._closed:
                raise self._error("not_loaded")
            active = self.active_workout
            if active is None:
                raise self._error("no_active")
            timestamp = dt_util.utcnow()
            cancelled = replace(
                active,
                completed_at=timestamp,
                duration_minutes=(timestamp - active.started_at).total_seconds() / 60,
                status="cancelled",
            )
            await self._commit(
                replace(
                    self.data,
                    workouts=tuple(
                        cancelled if item.workout_id == active.workout_id else item
                        for item in self.data.workouts
                    ),
                )
            )
            return cancelled

    async def async_log_exercise(
        self,
        exercise_id: str,
        variant: str,
        sets: list[int | float],
        rir: int,
        pain_score: int,
        notes: str = "",
    ) -> tuple[ExerciseLog, bool, str]:
        """Log an exercise or replace its prior log in the active workout."""
        async with self._lock:
            if self._closed:
                raise self._error("not_loaded")
            active = self.active_workout
            if active is None:
                raise self._error("no_active")
            if not any(
                definition.exercise_id == exercise_id
                for definition in self.data.exercise_definitions
            ):
                raise self._error("unknown_exercise")
            try:
                log = ExerciseLog.from_dict(
                    {
                        "exercise_id": exercise_id,
                        "variant": variant,
                        "sets": sets,
                        "rir": rir,
                        "pain_score": pain_score,
                        "notes": notes,
                    }
                )
            except InvalidExerciseLog as err:
                raise self._error(err.translation_key) from err
            replaced_existing = any(
                item.exercise_id == log.exercise_id for item in active.exercises
            )
            exercises = tuple(
                item for item in active.exercises if item.exercise_id != log.exercise_id
            ) + (log,)
            updated = replace(active, exercises=exercises)
            await self._commit(
                replace(
                    self.data,
                    workouts=tuple(
                        updated if item.workout_id == active.workout_id else item
                        for item in self.data.workouts
                    ),
                )
            )
            if pain_score >= 4:
                LOGGER.warning(
                    "Pain score threshold reached; consider stopping the painful "
                    "variant"
                )
            return log, replaced_existing, active.workout_id

    async def async_add_body_measurement(
        self,
        measured_at: str | datetime | None = None,
        weight_kg: int | float | None = None,
        waist_cm: int | float | None = None,
        resting_heart_rate: int | None = None,
        steps: int | None = None,
        sleep_hours: int | float | None = None,
        calorie_intake: int | float | None = None,
        protein_grams: int | float | None = None,
        notes: str = "",
    ) -> BodyMeasurement:
        """Validate, persist and publish one local health measurement."""
        async with self._lock:
            if self._closed:
                raise self._error("not_loaded")
            timestamp = self._timestamp(measured_at)
            if timestamp > dt_util.utcnow():
                raise self._error("future_timestamp")
            try:
                measurement = BodyMeasurement.from_dict(
                    {
                        "measurement_id": str(uuid4()),
                        "measured_at": timestamp,
                        "weight_kg": weight_kg,
                        "waist_cm": waist_cm,
                        "resting_heart_rate": resting_heart_rate,
                        "steps": steps,
                        "sleep_hours": sleep_hours,
                        "calorie_intake": calorie_intake,
                        "protein_grams": protein_grams,
                        "notes": notes,
                    }
                )
            except InvalidBodyMeasurement as err:
                raise self._error(err.translation_key) from err
            await self._commit(
                replace(
                    self.data,
                    body_measurements=(
                        *self.data.body_measurements,
                        measurement,
                    ),
                )
            )
            return measurement

    async def async_shutdown(self) -> None:
        """Wait for in-flight persistence and prevent further mutations."""
        async with self._lock:
            self._closed = True
            if self._remove_calendar_listener is not None:
                self._remove_calendar_listener()
                self._remove_calendar_listener = None
            self._listeners.clear()
