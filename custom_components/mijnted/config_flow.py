from typing import Optional
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, logger
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_CLIENT_ID
from .const import DOMAIN, DEFAULT_POLLING_INTERVAL
from .api import MijntedApi
import aiohttp

class MijnTedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # Mijn Ted configuration flow.

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                api = MijntedApi(
                    user_input["username"],
                    user_input["password"],
                    user_input["client_id"]
                )
                await self.hass.async_add_executor_job(api.authenticate)
                return self.async_create_entry(title="MijnTed", data=user_input)
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                logger.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Optional("polling_interval", default=DEFAULT_POLLING_INTERVAL.total_seconds()): int,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, user_input=None) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                api = MijntedApi(
                    user_input["username"],
                    user_input["password"],
                    user_input["client_id"]
                )
                await self.hass.async_add_executor_job(api.authenticate)
                existing_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
                self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
                return self.async_abort(reason="reauth_successful")
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                logger.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show the form to the user
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("client_id"): str,
                    vol.Optional("polling_interval", default=DEFAULT_POLLING_INTERVAL.total_seconds()): int,
                }
            ),
            errors=errors,
        )

