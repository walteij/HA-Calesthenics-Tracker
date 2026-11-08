"""Verify parameterless button entities delegate to the coordinator."""

import pytest
from homeassistant.components.button import ButtonEntityDescription

from custom_components.calisthenics_tracker.button import TrackerButton
from custom_components.calisthenics_tracker.const import PLATFORMS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "method_name"),
    (
        ("complete_workout", "async_complete_workout"),
        ("cancel_workout", "async_cancel_workout"),
    ),
)
async def test_workout_button_calls_coordinator_action(
    key: str, method_name: str
) -> None:
    called: list[str] = []

    class Coordinator:
        async def async_complete_workout(self) -> None:
            called.append("async_complete_workout")

        async def async_cancel_workout(self) -> None:
            called.append("async_cancel_workout")

    button = TrackerButton(Coordinator(), "entry", ButtonEntityDescription(key=key))

    await button.async_press()

    assert called == [method_name]
    assert button.entity_id == f"button.calisthenics_{key}"


def test_button_platform_is_forwarded_by_config_entry() -> None:
    assert "button" in {platform.value for platform in PLATFORMS}
