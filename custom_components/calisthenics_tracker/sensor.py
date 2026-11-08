"""Bounded sensor states derived from the local tracker."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CalisthenicsConfigEntry
from .calculations import (
    average_measurement_over_7_days,
    current_program_week,
    latest_measurement_value,
    next_workout,
    weekly_totals,
    weight_change_since_start,
)
from .coordinator import TrackerCoordinator
from .models import ExerciseDefinition
from .progression import (
    analyze_exercise_progress,
    beginner_graduation_readiness,
)

SENSORS = (
    SensorEntityDescription(
        key="active_workout", translation_key="active_workout", icon="mdi:weight-lifter"
    ),
    SensorEntityDescription(
        key="current_level",
        translation_key="current_level",
        icon="mdi:signal-cellular-3",
    ),
    SensorEntityDescription(
        key="current_week", translation_key="current_week", icon="mdi:calendar-week"
    ),
    SensorEntityDescription(
        key="next_workout",
        translation_key="next_workout",
        icon="mdi:calendar-arrow-right",
    ),
    SensorEntityDescription(
        key="sessions_this_week",
        translation_key="sessions_this_week",
        icon="mdi:calendar-check",
    ),
    SensorEntityDescription(
        key="training_minutes_this_week",
        translation_key="training_minutes_this_week",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="latest_weight",
        translation_key="latest_weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale",
    ),
    SensorEntityDescription(
        key="weight_7_day_average",
        translation_key="weight_7_day_average",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-line",
    ),
    SensorEntityDescription(
        key="weight_change_since_start",
        translation_key="weight_change_since_start",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:scale-balance",
    ),
    SensorEntityDescription(
        key="latest_waist",
        translation_key="latest_waist",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:tape-measure",
    ),
    SensorEntityDescription(
        key="average_daily_steps_7_days",
        translation_key="average_daily_steps_7_days",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shoe-print",
    ),
    SensorEntityDescription(
        key="average_sleep_7_days",
        translation_key="average_sleep_7_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
    ),
    SensorEntityDescription(
        key="beginner_graduation_readiness",
        translation_key="beginner_graduation_readiness",
        icon="mdi:medal-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalisthenicsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose workout and body-measurement sensors."""
    async_add_entities(
        [
            *(
                TrackerSensor(entry.runtime_data, entry.entry_id, description)
                for description in SENSORS
            ),
            *(
                ExerciseProgressSensor(entry.runtime_data, entry.entry_id, definition)
                for definition in entry.runtime_data.data.exercise_definitions
            ),
        ]
    )


class TrackerSensor(SensorEntity):
    """A push-updated sensor without unbounded history attributes."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: TrackerCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_id = f"sensor.calisthenics_{description.key}"

    async def async_added_to_hass(self) -> None:
        """Attach one listener, automatically removed when the entity unloads."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._tracker_changed))

    @callback
    def _tracker_changed(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | int | float | None:
        key = self.entity_description.key
        if key == "active_workout":
            active = self.coordinator.active_workout
            return active.session_type if active is not None else "idle"
        if key == "current_level":
            return self.coordinator.data.profile.current_level
        if key == "current_week":
            timezone = dt_util.get_time_zone(self.hass.config.time_zone)
            assert timezone is not None
            return current_program_week(
                self.coordinator.data.profile.start_date,
                dt_util.utcnow(),
                timezone,
            )
        if key == "next_workout":
            timezone = dt_util.get_time_zone(self.hass.config.time_zone)
            assert timezone is not None
            session_type, _ = next_workout(
                self.coordinator.data.workouts, dt_util.utcnow(), timezone
            )
            return session_type
        measurements = self.coordinator.data.body_measurements
        if key in ("latest_weight", "latest_waist"):
            field = "weight_kg" if key == "latest_weight" else "waist_cm"
            return latest_measurement_value(measurements, field)
        if key == "weight_change_since_start":
            return weight_change_since_start(measurements)
        if key == "beginner_graduation_readiness":
            return beginner_graduation_readiness(
                self.coordinator.data.workouts
            ).status.value
        timezone = dt_util.get_time_zone(self.hass.config.time_zone)
        assert timezone is not None
        if key in ("weight_7_day_average", "average_daily_steps_7_days"):
            field = "weight_kg" if key == "weight_7_day_average" else "steps"
            return average_measurement_over_7_days(
                measurements, field, dt_util.utcnow(), timezone
            )
        if key == "average_sleep_7_days":
            return average_measurement_over_7_days(
                measurements, "sleep_hours", dt_util.utcnow(), timezone
            )
        sessions, minutes = weekly_totals(
            self.coordinator.data.workouts, dt_util.utcnow(), timezone
        )
        return sessions if key == "sessions_this_week" else minutes

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        key = self.entity_description.key
        if key == "active_workout":
            active = self.coordinator.active_workout
            if active is None:
                return None
            return {
                "workout_id": active.workout_id,
                "started_at": active.started_at.isoformat(),
            }
        if key == "next_workout":
            timezone = dt_util.get_time_zone(self.hass.config.time_zone)
            assert timezone is not None
            _, scheduled_date = next_workout(
                self.coordinator.data.workouts, dt_util.utcnow(), timezone
            )
            return {"scheduled_date": scheduled_date.isoformat()}
        if key == "beginner_graduation_readiness":
            readiness = beginner_graduation_readiness(self.coordinator.data.workouts)
            return {
                "push_ups_reps": readiness.push_ups,
                "push_ups_target": 15,
                "dead_hang_pull_ups_reps": readiness.dead_hang_pull_ups,
                "dead_hang_pull_ups_target": 5,
                "strict_full_depth_squats_reps": readiness.strict_full_depth_squats,
                "strict_full_depth_squats_target": 20,
            }
        return None


class ExerciseProgressSensor(SensorEntity):
    """Expose one bounded progression result per catalog exercise."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: TrackerCoordinator,
        entry_id: str,
        definition: ExerciseDefinition,
    ) -> None:
        self.coordinator = coordinator
        self.definition = definition
        self._attr_unique_id = f"{entry_id}_progress_{definition.exercise_id}"
        self.entity_id = f"sensor.calisthenics_progress_{definition.exercise_id}"
        self._attr_name = f"{definition.name} progress"
        self._attr_icon = "mdi:chart-timeline-variant"

    async def async_added_to_hass(self) -> None:
        """Attach a push listener and remove it when unloaded."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._tracker_changed))

    @callback
    def _tracker_changed(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        return analyze_exercise_progress(
            self.definition.exercise_id,
            self.coordinator.data.exercise_definitions,
            self.coordinator.data.workouts,
        ).status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        progress = analyze_exercise_progress(
            self.definition.exercise_id,
            self.coordinator.data.exercise_definitions,
            self.coordinator.data.workouts,
        )
        attributes: dict[str, Any] = {
            "exercise_id": self.definition.exercise_id,
            "variant": progress.variant,
            "minimum_repetitions": self.definition.minimum_repetitions,
            "maximum_repetitions": self.definition.maximum_repetitions,
            "recent_sessions": [
                {
                    "completed_at": session.completed_at,
                    "total_repetitions": session.total_repetitions,
                    "set_count": session.set_count,
                    "rir": session.rir,
                    "pain_score": session.pain_score,
                }
                for session in progress.recent_sessions
            ],
        }
        if progress.status.value == "regression_recommended":
            attributes["suggested_regression"] = self.definition.regression
        if progress.status.value == "progression_ready":
            attributes["suggested_progression"] = self.definition.progression
        return attributes
