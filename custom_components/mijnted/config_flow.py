from typing import Any, Dict, Optional
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, DEFAULT_POLLING_INTERVAL
from .api import MijntedApi, MijntedApiError
import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
    pass

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
    pass

class MijnTedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a MijnTed config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client_id: Optional[str] = None
        self._refresh_token: Optional[str] = None

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                # Ensure polling_interval is set with default if not provided
                if "polling_interval" not in user_input:
                    user_input["polling_interval"] = int(DEFAULT_POLLING_INTERVAL.total_seconds())
                await self._validate_input(user_input)
                return self.async_create_entry(
                    title="MijnTed",
                    data=user_input
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required("refresh_token"): str,
                    vol.Optional(
                        "polling_interval",
                        default=DEFAULT_POLLING_INTERVAL.total_seconds()
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=900, max=86400)  # 15 minutes to 24 hours
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle reauthorization flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle reauthorization confirmation."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                # Ensure polling_interval is set with default if not provided
                if "polling_interval" not in user_input:
                    user_input["polling_interval"] = int(DEFAULT_POLLING_INTERVAL.total_seconds())
                await self._validate_input(user_input)
                existing_entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required("refresh_token"): str,
                    vol.Optional(
                        "polling_interval",
                        default=DEFAULT_POLLING_INTERVAL.total_seconds()
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=900, max=86400)  # 15 minutes to 24 hours
                    ),
                }
            ),
            errors=errors,
        )

    async def _validate_input(self, user_input: Dict[str, Any]) -> None:
        """Validate the user input."""
        try:
            api = MijntedApi(
                client_id=user_input[CONF_CLIENT_ID],
                refresh_token=user_input["refresh_token"]
            )
            async with api:
                await api.authenticate()
                # Store the updated refresh token if it was refreshed
                if api.refresh_token != user_input["refresh_token"]:
                    user_input["refresh_token"] = api.refresh_token
        except MijntedApiError as err:
            if "Authentication failed" in str(err) or "Token refresh failed" in str(err):
                raise InvalidAuth from err
            raise CannotConnect from err
        except aiohttp.ClientError as err:
            raise CannotConnect from err

