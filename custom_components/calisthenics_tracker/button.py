"""Parameterless workout actions exposed as buttons."""

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CalisthenicsConfigEntry
from .coordinator import TrackerCoordinator

BUTTONS = (
    ButtonEntityDescription(
        key="complete_workout",
        translation_key="complete_workout",
        icon="mdi:check-circle-outline",
    ),
    ButtonEntityDescription(
        key="cancel_workout",
        translation_key="cancel_workout",
        icon="mdi:cancel",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalisthenicsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the two parameterless workout buttons."""
    async_add_entities(
        TrackerButton(entry.runtime_data, entry.entry_id, description)
        for description in BUTTONS
    )


class TrackerButton(ButtonEntity):
    """Delegate a parameterless workout action to the coordinator."""

    def __init__(
        self,
        coordinator: TrackerCoordinator,
        entry_id: str,
        description: ButtonEntityDescription,
    ) -> None:
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_id = f"button.calisthenics_{description.key}"

    async def async_press(self) -> None:
        """Complete or cancel the currently active workout."""
        if self.entity_description.key == "complete_workout":
            await self.coordinator.async_complete_workout()
        else:
            await self.coordinator.async_cancel_workout()
