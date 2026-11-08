"""Config-flow behavior with explicit method stubs."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.calisthenics_tracker.config_flow import CalisthenicsConfigFlow


@pytest.mark.asyncio
async def test_config_flow_returns_form() -> None:
    flow = CalisthenicsConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = lambda: None
    flow._async_current_entries = lambda: []
    flow.async_show_form = lambda **kwargs: {"type": "form", **kwargs}

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_config_flow_creates_entry_for_valid_input() -> None:
    flow = CalisthenicsConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = lambda: None
    flow._async_current_entries = lambda: []
    flow.async_create_entry = lambda **kwargs: {"type": "create_entry", **kwargs}

    result = await flow.async_step_user(
        {
            "name": "Walter",
            "start_date": "2026-11-08",
            "current_level": "beginner",
            "goal": "Become stronger",
            "target_sessions_per_week": 3,
            "daily_step_target": 8000,
        }
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Walter"


@pytest.mark.asyncio
async def test_config_flow_rejects_duplicate_instance() -> None:
    flow = CalisthenicsConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = lambda: None
    flow._async_current_entries = lambda: [object()]
    flow.async_abort = lambda **kwargs: {"type": "abort", **kwargs}

    result = await flow.async_step_user()
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_config_flow_reports_future_date_and_allows_recovery() -> None:
    flow = CalisthenicsConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = lambda: None
    flow._async_current_entries = lambda: []
    flow.async_show_form = lambda **kwargs: {"type": "form", **kwargs}
    flow.async_create_entry = lambda **kwargs: {"type": "create_entry", **kwargs}

    user_input = {
        "name": "Walter",
        "start_date": (dt_util.now().date() + timedelta(days=1)).isoformat(),
        "current_level": "beginner",
        "goal": "Become stronger",
        "target_sessions_per_week": 3,
        "daily_step_target": 8000,
    }
    result = await flow.async_step_user(user_input)
    assert result["errors"] == {"start_date": "future_start_date"}

    user_input["start_date"] = dt_util.now().date().isoformat()
    recovered = await flow.async_step_user(user_input)
    assert recovered["type"] == "create_entry"


@pytest.mark.asyncio
async def test_config_flow_reports_invalid_profile_input() -> None:
    flow = CalisthenicsConfigFlow()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = lambda: None
    flow._async_current_entries = lambda: []
    flow.async_show_form = lambda **kwargs: {"type": "form", **kwargs}

    result = await flow.async_step_user({"name": "Missing required fields"})

    assert result["errors"] == {"base": "invalid_profile"}
