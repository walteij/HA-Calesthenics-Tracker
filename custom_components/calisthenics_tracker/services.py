"""Service schemas and registrations for tracker actions."""

from __future__ import annotations

from math import isfinite

import probatio
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_ADD_BODY_MEASUREMENT,
    SERVICE_CANCEL,
    SERVICE_COMPLETE,
    SERVICE_LOG_EXERCISE,
    SERVICE_START,
    SESSION_TYPES,
)
from .coordinator import TrackerCoordinator

START_SCHEMA = probatio.Schema(
    {
        probatio.Required("session_type"): probatio.In(SESSION_TYPES),
        probatio.Optional("started_at"): str,
    }
)
COMPLETE_SCHEMA = probatio.Schema(
    {
        probatio.Optional("completed_at"): str,
        probatio.Optional("notes", default=""): cv.string,
    }
)
CANCEL_SCHEMA = probatio.Schema({})


def _sets(value: object) -> list[int | float]:
    if not isinstance(value, list) or not value:
        raise ValueError("Sets must be a non-empty list")
    if any(not _valid_set(item) for item in value):
        raise ValueError("Each set must be a positive number")
    return value


def _valid_set(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return isfinite(value) and value > 0
    except OverflowError:
        return False


def _score(value: object, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Score is outside its allowed range")
    return value


def _rir(value: object) -> int:
    return _score(value, 5)


def _pain_score(value: object) -> int:
    return _score(value, 10)


def _measurement_number(
    value: object,
    *,
    minimum: float,
    maximum: float | None = None,
    exclusive: bool = False,
) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Measurement must be numeric")
    try:
        if not isfinite(value):
            raise ValueError("Measurement must be finite")
    except OverflowError as err:
        raise ValueError("Measurement must be finite") from err
    if (value <= minimum if exclusive else value < minimum) or (
        maximum is not None and value > maximum
    ):
        raise ValueError("Measurement is outside its allowed range")
    return value


def _weight(value: object) -> int | float:
    return _measurement_number(value, minimum=0, maximum=500, exclusive=True)


def _waist(value: object) -> int | float:
    return _measurement_number(value, minimum=0, maximum=300, exclusive=True)


def _nonnegative_measurement(value: object) -> int | float:
    return _measurement_number(value, minimum=0)


def _sleep_hours(value: object) -> int | float:
    return _measurement_number(value, minimum=0, maximum=24)


def _heart_rate(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 300:
        raise ValueError("Resting heart rate must be an integer from 1 to 300")
    return value


def _steps(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Steps must be a non-negative integer")
    return value


LOG_EXERCISE_SCHEMA = probatio.Schema(
    {
        probatio.Required("exercise_id"): cv.string,
        probatio.Required("variant"): cv.string,
        probatio.Required("sets"): _sets,
        probatio.Required("rir"): _rir,
        probatio.Required("pain_score"): _pain_score,
        probatio.Optional("notes", default=""): cv.string,
    }
)
ADD_BODY_MEASUREMENT_SCHEMA = probatio.Schema(
    {
        probatio.Optional("measured_at"): str,
        probatio.Optional("weight_kg"): _weight,
        probatio.Optional("waist_cm"): _waist,
        probatio.Optional("resting_heart_rate"): _heart_rate,
        probatio.Optional("steps"): _steps,
        probatio.Optional("sleep_hours"): _sleep_hours,
        probatio.Optional("calorie_intake"): _nonnegative_measurement,
        probatio.Optional("protein_grams"): _nonnegative_measurement,
        probatio.Optional("notes", default=""): cv.string,
    }
)


def loaded_coordinator(hass: HomeAssistant) -> TrackerCoordinator:
    """Return the loaded runtime coordinator, or a translatable service error."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="not_loaded"
    )


def register_services(hass: HomeAssistant) -> None:
    """Register actions once while at least one config entry is loaded."""

    async def start(call: ServiceCall) -> ServiceResponse:
        workout = await loaded_coordinator(hass).async_start_workout(
            call.data["session_type"], call.data.get("started_at")
        )
        return {"workout_id": workout.workout_id}

    async def complete(call: ServiceCall) -> ServiceResponse:
        workout = await loaded_coordinator(hass).async_complete_workout(
            call.data.get("completed_at"), call.data["notes"]
        )
        return {
            "workout_id": workout.workout_id,
            "duration_minutes": workout.duration_minutes,
        }

    async def cancel(call: ServiceCall) -> ServiceResponse:
        workout = await loaded_coordinator(hass).async_cancel_workout()
        return {"workout_id": workout.workout_id, "status": workout.status}

    async def log_exercise(call: ServiceCall) -> ServiceResponse:
        coordinator = loaded_coordinator(hass)
        log, replaced_existing, workout_id = await coordinator.async_log_exercise(
            call.data["exercise_id"],
            call.data["variant"],
            call.data["sets"],
            call.data["rir"],
            call.data["pain_score"],
            call.data["notes"],
        )
        return {
            "workout_id": workout_id,
            "exercise_id": log.exercise_id,
            "replaced_existing": replaced_existing,
            "pain_warning": log.pain_score >= 4,
        }

    async def add_body_measurement(call: ServiceCall) -> ServiceResponse:
        measurement = await loaded_coordinator(hass).async_add_body_measurement(
            **call.data
        )
        return {
            "measurement_id": measurement.measurement_id,
            "measured_at": measurement.measured_at.isoformat(),
        }

    for name, handler, schema in (
        (SERVICE_START, start, START_SCHEMA),
        (SERVICE_COMPLETE, complete, COMPLETE_SCHEMA),
        (SERVICE_CANCEL, cancel, CANCEL_SCHEMA),
        (SERVICE_LOG_EXERCISE, log_exercise, LOG_EXERCISE_SCHEMA),
        (
            SERVICE_ADD_BODY_MEASUREMENT,
            add_body_measurement,
            ADD_BODY_MEASUREMENT_SCHEMA,
        ),
    ):
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(
                DOMAIN,
                name,
                handler,
                schema=schema,
                supports_response=SupportsResponse.OPTIONAL,
            )


def unregister_services(hass: HomeAssistant, unloading_entry_id: str) -> None:
    """Remove tracker actions when unloading the last active config entry."""
    if any(
        entry.entry_id != unloading_entry_id and entry.state is ConfigEntryState.LOADED
        for entry in hass.config_entries.async_entries(DOMAIN)
    ):
        return
    for name in (
        SERVICE_START,
        SERVICE_COMPLETE,
        SERVICE_CANCEL,
        SERVICE_LOG_EXERCISE,
        SERVICE_ADD_BODY_MEASUREMENT,
    ):
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)
