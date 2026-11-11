"""Workout focus selection that drives the suggestion entities."""

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import CalisthenicsConfigEntry
from .const import WORKOUT_FOCI
from .suggestion import WorkoutSuggestion, suggestion_device_info

SUGGESTION_FOCUS = SelectEntityDescription(
    key="suggestion_focus",
    translation_key="suggestion_focus",
    icon="mdi:target",
    options=list(WORKOUT_FOCI),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalisthenicsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the workout focus select."""
    async_add_entities(
        [SuggestionFocusSelect(entry.runtime_data.workout_suggestion, entry.entry_id)]
    )


class SuggestionFocusSelect(SelectEntity, RestoreEntity):
    """Choose the goal for the generated workout suggestion."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, suggestion: WorkoutSuggestion, entry_id: str) -> None:
        self.suggestion = suggestion
        self.entity_description = SUGGESTION_FOCUS
        self._attr_unique_id = f"{entry_id}_{SUGGESTION_FOCUS.key}"
        self._attr_device_info = suggestion_device_info(entry_id)
        self.entity_id = f"select.calisthenics_{SUGGESTION_FOCUS.key}"

    async def async_added_to_hass(self) -> None:
        """Restore the last focus so the suggestion survives a restart."""
        await super().async_added_to_hass()
        self.async_on_remove(self.suggestion.async_add_listener(self._focus_changed))
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in WORKOUT_FOCI:
            self.suggestion.async_set_focus(last_state.state)

    @callback
    def _focus_changed(self) -> None:
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        return self.suggestion.focus

    async def async_select_option(self, option: str) -> None:
        """Recalculate the suggestion for the chosen focus."""
        self.suggestion.async_set_focus(option)
