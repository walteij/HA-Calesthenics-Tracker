"""Single persistence boundary using Home Assistant's asynchronous Store."""

from copy import deepcopy
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util.file import WriteError

from .const import DOMAIN, STORAGE_VERSION
from .exercise_catalog import WORKBOOK_EXERCISES
from .models import InvalidTrackerData, Profile, TrackerData


def migrate_payload(old_version: int, payload: Any) -> dict[str, Any]:
    """Upgrade prior profile/workout schemas while retaining all existing records."""
    if old_version not in (0, 1, 2, 3) or not isinstance(payload, dict):
        raise InvalidTrackerData("Unsupported storage migration")
    migrated = deepcopy(payload)
    if migrated.get("schema_version", old_version) != old_version:
        raise InvalidTrackerData("Inconsistent migration version")
    if old_version < 2:
        for workout in migrated.get("workouts", []):
            if not isinstance(workout, dict):
                raise InvalidTrackerData("Invalid legacy workout")
            workout.setdefault("exercises", [])
    exercise_definitions = migrated.get("exercise_definitions")
    if not exercise_definitions:
        migrated["exercise_definitions"] = [
            exercise.to_dict() for exercise in WORKBOOK_EXERCISES
        ]
    elif isinstance(exercise_definitions, list) and all(
        isinstance(item, dict) and isinstance(item.get("exercise_id"), str)
        for item in exercise_definitions
    ):
        existing_ids = {item["exercise_id"] for item in exercise_definitions}
        exercise_definitions.extend(
            exercise.to_dict()
            for exercise in WORKBOOK_EXERCISES
            if exercise.exercise_id not in existing_ids
        )
    migrated["schema_version"] = STORAGE_VERSION
    migrated.setdefault("body_measurements", [])
    return TrackerData.from_dict(migrated).to_dict()


class _VersionedStore(Store[dict[str, Any]]):
    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: Any
    ) -> dict[str, Any]:
        return migrate_payload(old_major_version, old_data)

    async def _async_write_data(self, data: dict[str, Any]) -> None:
        # Core logs WriteError without raising it; actions must not report success.
        try:
            await super()._async_write_data(data)
        except WriteError as err:
            raise OSError("Tracker storage write failed") from err


class TrackerStorage:
    """Load, validate and durably save all tracker records in one place."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._store = _VersionedStore(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
            private=True,
            atomic_writes=True,
        )

    async def async_load(self, initial_profile: Profile) -> TrackerData:
        """Initialize only absent storage; invalid existing data must fail."""
        existed = await self._hass.async_add_executor_job(Path(self._store.path).exists)
        payload = await self._store.async_load()
        if payload is None:
            if existed:
                raise InvalidTrackerData("Existing storage could not be loaded")
            data = TrackerData(initial_profile, exercise_definitions=WORKBOOK_EXERCISES)
            await self.async_save(data)
            return data
        return TrackerData.from_dict(payload)

    async def async_save(self, data: TrackerData) -> None:
        """Await durable persistence before an action is acknowledged."""
        payload = data.to_dict()
        TrackerData.from_dict(payload)
        await self._store.async_save(payload)

    async def async_remove(self) -> None:
        """Delete this entry's private persisted profile and training records."""
        await self._store.async_remove()
