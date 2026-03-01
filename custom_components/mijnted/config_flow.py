import logging
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_PASSWORD,
    CONF_POLLING_INTERVAL,
    CONF_USERNAME,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
    MAX_POLLING_INTERVAL,
    MIN_POLLING_INTERVAL,
)
from .auth import MijntedAuth
from .exceptions import (
    MijntedApiError,
    MijntedAuthenticationError,
    MijntedConnectionError,
    MijntedGrantExpiredError,
    MijntedTimeoutError,
)

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
        """Create options flow handler.

        Args:
            config_entry: The config entry to create options flow for.

        Returns:
            The options flow handler instance.
        """
        return MijnTedOptionsFlowHandler(config_entry)

    def _handle_validation_error(
        self,
        err: Exception,
        error_type: str,
        log_message: str,
        exception_class: type,
        user_message_template: str
    ) -> None:
        """Log validation error and raise the appropriate exception."""
        error_msg = str(err) if err else ""
        _LOGGER.debug(
            f"{log_message}: %s",
            error_msg,
            extra={"error_type": error_type}
        )
        user_message = user_message_template.format(msg=error_msg) if error_msg else user_message_template.replace("{msg}", "")
        raise exception_class(user_message) from err
    
    def _ensure_polling_interval_default(self, user_input: Dict[str, Any]) -> None:
        """Set default polling interval on user_input if missing."""
        if CONF_POLLING_INTERVAL not in user_input:
            user_input[CONF_POLLING_INTERVAL] = int(DEFAULT_POLLING_INTERVAL.total_seconds())

    @staticmethod
    def _get_data_schema() -> vol.Schema:
        """Return the data schema for the config form."""
        return vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(
                    CONF_POLLING_INTERVAL,
                    default=DEFAULT_POLLING_INTERVAL.total_seconds()
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLLING_INTERVAL, max=MAX_POLLING_INTERVAL)
                )
            }
        )

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step.

        Args:
            user_input: User-provided configuration data, or None if not yet submitted.

        Returns:
            FlowResult: The next step in the config flow.
        """
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                self._ensure_polling_interval_default(user_input)
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
        """Handle reauthorization flow.

        Args:
            user_input: User-provided data, or None if not yet submitted.

        Returns:
            FlowResult: The next step in the reauth flow.
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle reauthorization confirmation.

        Args:
            user_input: User-provided credentials, or None if not yet submitted.

        Returns:
            FlowResult: The next step in the reauth flow.
        """
        errors: Dict[str, str] = {}

        if user_input is not None:
            try:
                self._ensure_polling_interval_default(user_input)
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
        """Validate credentials and populate tokens in user_input."""
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
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD]
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
            self._handle_validation_error(err, "MijntedGrantExpiredError", "Grant expiration during validation", InvalidAuth, "Refresh token has expired. Please re-authenticate: {msg}")
        except MijntedAuthenticationError as err:
            self._handle_validation_error(err, "MijntedAuthenticationError", "Authentication validation failed", InvalidAuth, "Invalid credentials: {msg}")
        except MijntedTimeoutError as err:
            self._handle_validation_error(err, "MijntedTimeoutError", "Timeout during validation", CannotConnect, "Connection timeout: {msg}. Please check your internet connection and try again.")
        except MijntedConnectionError as err:
            self._handle_validation_error(err, "MijntedConnectionError", "Connection validation failed", CannotConnect, "Unable to connect to MijnTed API: {msg}. Please check your internet connection.")
        except MijntedApiError as err:
            self._handle_validation_error(err, "MijntedApiError", "API validation failed", CannotConnect, "MijnTed API error: {msg}. Please try again later.")
        except aiohttp.ClientError as err:
            self._handle_validation_error(err, "aiohttp.ClientError", "HTTP client error during validation", CannotConnect, "Network error: {msg}. Please check your internet connection.")
        finally:
            await session.close()


class MijnTedOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for MijnTed.

    Manages the options configuration UI for an existing MijnTed integration
    instance (e.g. polling interval).

    Args:
        config_entry: The ConfigEntry to configure options for.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow.

        Args:
            config_entry: The config entry being configured.
        """
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options.

        Args:
            user_input: User-provided options, or None if not yet submitted.

        Returns:
            FlowResult: The next step in the options flow.
        """
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
                        CONF_POLLING_INTERVAL,
                        default=self.config_entry.data.get(
                            CONF_POLLING_INTERVAL,
                            DEFAULT_POLLING_INTERVAL.total_seconds()
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_POLLING_INTERVAL, max=MAX_POLLING_INTERVAL)
                    )
                }
            ),
        )

