"""A fully local, single-profile calisthenics integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import TrackerCoordinator
from .models import InvalidTrackerData, Profile
from .services import register_services, unregister_services
from .storage import TrackerStorage

LOGGER = logging.getLogger(__name__)
type CalisthenicsConfigEntry = ConfigEntry[TrackerCoordinator]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Allow the integration domain to load before its config entry."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: CalisthenicsConfigEntry
) -> None:
    """Load valid storage before forwarding platforms or exposing actions."""
    storage = TrackerStorage(hass, entry.entry_id)
    try:
        data = await storage.async_load(Profile.from_dict(dict(entry.data)))
    except (InvalidTrackerData, KeyError, TypeError, OSError) as err:
        LOGGER.error("Tracker setup refused: invalid or inaccessible local storage")
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="invalid_storage"
        ) from err
    coordinator = TrackerCoordinator(hass, storage, data)
    entry.runtime_data = coordinator
    ready = False
    try:
        coordinator.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        register_services(hass)
        ready = True
    finally:
        if not ready:
            await coordinator.async_shutdown()
    return None


async def async_unload_entry(
    hass: HomeAssistant, entry: CalisthenicsConfigEntry
) -> None:
    """Remove listeners and actions after successful platform unload."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.async_shutdown()
    unregister_services(hass, entry.entry_id)
    return None


async def async_remove_entry(
    hass: HomeAssistant, entry: CalisthenicsConfigEntry
) -> None:
    """Delete private tracker data when the user removes the config entry."""
    await TrackerStorage(hass, entry.entry_id).async_remove()
