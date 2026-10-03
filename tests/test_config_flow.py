"""Tests for config_flow.py."""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from custom_components.mijnted.config_flow import (
    MijnTedConfigFlow,
    MijnTedOptionsFlowHandler,
)
from custom_components.mijnted.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_POLLING_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.const import CONF_CLIENT_ID


class TestOptionsFlowFactory:
    """Verify the config flow options handler factory behavior."""

    def test_returns_options_flow_handler_directly(self):
        """Calling async_get_options_flow -> returns handler, not coroutine."""
        config_entry = object()

        handler = MijnTedConfigFlow.async_get_options_flow(config_entry)

        assert isinstance(handler, MijnTedOptionsFlowHandler)
        assert handler.config_entry is config_entry
        assert not inspect.iscoroutine(handler)


class TestReauthentication:
    """Verify reauthentication preserves existing configuration values."""

    def test_schema_uses_existing_name_and_polling_defaults(self):
        """Existing entry data -> reauthentication schema preserves its defaults."""
        schema = MijnTedConfigFlow._get_data_schema(
            {CONF_NAME: "Home", CONF_POLLING_INTERVAL: 7200}
        )

        result = schema(
            {
                CONF_CLIENT_ID: "client",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "password",
            }
        )

        assert result[CONF_NAME] == "Home"
        assert result[CONF_POLLING_INTERVAL] == 7200

    def test_schema_does_not_expose_stored_password(self):
        """Stored password -> reauthentication schema still requires fresh input."""
        schema = MijnTedConfigFlow._get_data_schema(
            {
                CONF_CLIENT_ID: "client",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "stored-password",
            }
        )

        with pytest.raises(vol.Invalid):
            schema({})

    async def test_success_preserves_data_and_updates_title(self):
        """Successful reauthentication -> custom name and existing data are retained."""
        flow = MijnTedConfigFlow()
        flow.context = {"entry_id": "entry_one"}
        flow.hass = MagicMock()
        flow.hass.config_entries.async_reload = AsyncMock()
        flow.async_abort = MagicMock(return_value={"type": "abort"})
        flow._validate_input = AsyncMock()

        existing_entry = MagicMock()
        existing_entry.entry_id = "entry_one"
        existing_entry.data = {
            CONF_NAME: "Home",
            CONF_POLLING_INTERVAL: 7200,
            "refresh_token": "existing-token",
        }
        flow.hass.config_entries.async_get_entry.return_value = existing_entry

        user_input = {
            CONF_CLIENT_ID: "client",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
            CONF_NAME: "Home",
            CONF_POLLING_INTERVAL: 7200,
        }
        result = await flow.async_step_reauth_confirm(user_input)

        assert result == {"type": "abort"}
        flow.hass.config_entries.async_update_entry.assert_called_once_with(
            existing_entry,
            title="Home",
            data={
                **existing_entry.data,
                **user_input,
            },
        )
        flow.hass.config_entries.async_reload.assert_awaited_once_with("entry_one")
