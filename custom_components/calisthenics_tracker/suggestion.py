"""Selected workout focus and the suggestion derived from tracker data."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import (
    DEFAULT_SUGGESTION_FOCUS,
    DOMAIN,
    SUGGESTION_DEVICE_NAME,
    WORKOUT_FOCI,
)
from .workout_plans import WorkoutPlanUnavailable, suggest_workout

if TYPE_CHECKING:
    from .coordinator import TrackerCoordinator


class WorkoutSuggestion:
    """Keep one suggestion in sync with the selected focus and tracker data."""

    def __init__(self, coordinator: TrackerCoordinator) -> None:
        self._coordinator = coordinator
        self._listeners: set[Callable[[], None]] = set()
        self.focus = DEFAULT_SUGGESTION_FOCUS
        self.result: dict[str, Any] | None = None
        self._recalculate()
        coordinator.async_add_listener(self._tracker_changed)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity and return its unload callback."""
        self._listeners.add(listener)

        @callback
        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    @callback
    def async_set_focus(self, focus: str) -> None:
        """Select a new focus and publish the matching suggestion."""
        if focus not in WORKOUT_FOCI:
            raise ValueError(f"Unsupported workout focus: {focus}")
        if focus == self.focus and self.result is not None:
            return
        self.focus = focus
        self._recalculate()
        self._notify()

    @callback
    def _tracker_changed(self) -> None:
        # Level or catalog changes alter the suggestion for the same focus.
        self._recalculate()
        self._notify()

    def _recalculate(self) -> None:
        data = self._coordinator.data
        try:
            self.result = suggest_workout(
                self.focus, data.profile.current_level, data.exercise_definitions
            )
        except WorkoutPlanUnavailable:
            self.result = None

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()


def suggestion_device_info(entry_id: str) -> DeviceInfo:
    """Group the suggestion entities under one service device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_workout_suggestion")},
        name=SUGGESTION_DEVICE_NAME,
        entry_type=DeviceEntryType.SERVICE,
    )
