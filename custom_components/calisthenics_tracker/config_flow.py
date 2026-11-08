"""UI configuration for a single local training profile."""

from typing import Any

import probatio
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_DAILY_STEP_TARGET,
    DEFAULT_SESSIONS_PER_WEEK,
    DOMAIN,
    LEVELS,
)
from .models import InvalidTrackerData, Profile


class CalisthenicsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the singleton tracker without collecting external credentials."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the profile and prevent duplicate and concurrent entries."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalized = dict(user_input)
                # Number selectors submit floats even for integer-sized steps.
                for key in ("target_sessions_per_week", "daily_step_target"):
                    value = normalized[key]
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not float(value).is_integer()
                    ):
                        raise InvalidTrackerData(f"Invalid {key}")
                    normalized[key] = int(value)
                profile = Profile.from_dict(normalized)
                if profile.start_date > dt_util.now().date():
                    errors["start_date"] = "future_start_date"
                else:
                    return self.async_create_entry(
                        title=profile.name, data=profile.to_dict()
                    )
            except InvalidTrackerData, KeyError, OverflowError:
                errors["base"] = "invalid_profile"
        schema = probatio.Schema(
            {
                probatio.Required("name"): selector.TextSelector(),
                probatio.Required(
                    "start_date", default=dt_util.now().date().isoformat()
                ): selector.DateSelector(),
                probatio.Required(
                    "current_level", default="beginner"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(LEVELS), translation_key="level"
                    )
                ),
                probatio.Required("goal"): selector.TextSelector(),
                probatio.Required(
                    "target_sessions_per_week", default=DEFAULT_SESSIONS_PER_WEEK
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=7, step=1, mode="box")
                ),
                probatio.Required(
                    "daily_step_target", default=DEFAULT_DAILY_STEP_TARGET
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=100000, step=1, mode="box")
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            last_step=True,
        )
