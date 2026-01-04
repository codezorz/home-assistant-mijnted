from typing import Any, Dict, Optional
from datetime import datetime
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, DEFAULT_POLLING_INTERVAL, MIN_POLLING_INTERVAL, MAX_POLLING_INTERVAL
from .auth import MijntedAuth
from .exceptions import (
    MijntedApiError,
    MijntedAuthenticationError,
    MijntedGrantExpiredError,
    MijntedConnectionError,
    MijntedTimeoutError,
)
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

    @staticmethod
    async def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create options flow handler."""
        return MijnTedOptionsFlowHandler(config_entry)

    @staticmethod
    def _get_data_schema() -> vol.Schema:
        """Get the data schema for config flow."""
        return vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Optional(
                    "polling_interval",
                    default=DEFAULT_POLLING_INTERVAL.total_seconds()
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLLING_INTERVAL, max=MAX_POLLING_INTERVAL)
                )
            }
        )

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
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
            data_schema=self._get_data_schema(),
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
            data_schema=self._get_data_schema(),
            errors=errors,
        )

    async def _validate_input(self, user_input: Dict[str, Any]) -> None:
        """Validate the user input."""
        # Create session with explicit cookie jar to ensure cookies are maintained between requests
        connector = aiohttp.TCPConnector()
        cookie_jar = aiohttp.CookieJar()
        session = aiohttp.ClientSession(connector=connector, cookie_jar=cookie_jar)
        try:
            auth = MijntedAuth(
                hass=self.hass,
                session=session,
                client_id=user_input[CONF_CLIENT_ID]
            )
            tokens = await auth.async_authenticate_with_credentials(
                username=user_input["username"],
                password=user_input["password"]
            )
            
            user_input["refresh_token"] = tokens.get("refresh_token")
            user_input["access_token"] = tokens.get("access_token") or tokens.get("id_token")
            
            refresh_token_expires_at = tokens.get("refresh_token_expires_at")
            if refresh_token_expires_at:
                if isinstance(refresh_token_expires_at, datetime):
                    user_input["refresh_token_expires_at"] = refresh_token_expires_at.isoformat()
                else:
                    user_input["refresh_token_expires_at"] = refresh_token_expires_at
            
            if not user_input.get("refresh_token"):
                raise InvalidAuth("Failed to obtain refresh token")
            
            if not user_input.get("access_token"):
                raise InvalidAuth("Failed to obtain access token")
            
            auth.access_token = user_input["access_token"]
            auth.refresh_token = user_input["refresh_token"]
            id_token = tokens.get("id_token")
            if id_token:
                await auth._populate_claims_from_id_token(id_token)
            if auth.residential_unit:
                user_input["residential_unit"] = auth.residential_unit
        except MijntedGrantExpiredError as err:
            error_msg = str(err) if err else "Refresh token grant has expired"
            _LOGGER.debug(
                "Grant expiration during validation: %s",
                error_msg,
                extra={"error_type": "MijntedGrantExpiredError"}
            )
            raise InvalidAuth(f"Refresh token has expired. Please re-authenticate: {error_msg}") from err
        except MijntedAuthenticationError as err:
            error_msg = str(err) if err else "Authentication failed"
            _LOGGER.debug(
                "Authentication validation failed: %s",
                error_msg,
                extra={"error_type": "MijntedAuthenticationError"}
            )
            raise InvalidAuth(f"Invalid credentials: {error_msg}") from err
        except MijntedTimeoutError as err:
            error_msg = str(err) if err else "Request timed out"
            _LOGGER.debug(
                "Timeout during validation: %s",
                error_msg,
                extra={"error_type": "MijntedTimeoutError"}
            )
            raise CannotConnect(f"Connection timeout: {error_msg}. Please check your internet connection and try again.") from err
        except MijntedConnectionError as err:
            error_msg = str(err) if err else "Connection failed"
            _LOGGER.debug(
                "Connection validation failed: %s",
                error_msg,
                extra={"error_type": "MijntedConnectionError"}
            )
            raise CannotConnect(f"Unable to connect to MijnTed API: {error_msg}. Please check your internet connection.") from err
        except MijntedApiError as err:
            error_msg = str(err) if err else "API error"
            _LOGGER.debug(
                "API validation failed: %s",
                error_msg,
                extra={"error_type": "MijntedApiError"}
            )
            raise CannotConnect(f"MijnTed API error: {error_msg}. Please try again later.") from err
        except aiohttp.ClientError as err:
            error_msg = str(err) if err else "Network error"
            _LOGGER.debug(
                "HTTP client error during validation: %s",
                error_msg,
                extra={"error_type": "aiohttp.ClientError"}
            )
            raise CannotConnect(f"Network error: {error_msg}. Please check your internet connection.") from err
        finally:
            await session.close()


class MijnTedOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for MijnTed."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            updated_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=updated_data,
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "polling_interval",
                        default=self.config_entry.data.get(
                            "polling_interval",
                            DEFAULT_POLLING_INTERVAL.total_seconds()
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_POLLING_INTERVAL, max=MAX_POLLING_INTERVAL)
                    )
                }
            ),
        )

