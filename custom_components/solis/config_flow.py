"""Config flow for Solis integration."""
import logging
import os

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import selector
from homeassistant.const import (
    CONF_NAME,
)
from .const import (
    DOMAIN,
    CONF_PORTAL_DOMAIN,
    CONF_PORTAL_VERSION,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SECRET,
    CONF_KEY_ID,
    CONF_PLANT_ID,
    SENSOR_PREFIX,
    DEFAULT_DOMAIN,
#    SENSOR_TYPES,
)
from .ginlong_api import GinlongConfig, GinlongAPI
from .soliscloud_api import SoliscloudConfig, SoliscloudAPI

_LOGGER = logging.getLogger(__name__)

class SolisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solis."""

    VERSION = 1
    _data = None

    async def async_step_user(self, user_input=None):
        """Select server url and API version."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data = user_input
            if user_input.get(CONF_PORTAL_VERSION) == "ginlong_v2":
                _LOGGER.debug("Ginlong.")
                return await self.async_step_credentials_password(user_input)
            _LOGGER.debug("Soliscloud.")
            return await self.async_step_credentials_secret(user_input)

        data_schema= {
            vol.Required(CONF_NAME, default=SENSOR_PREFIX): cv.string,
            vol.Required(CONF_PORTAL_DOMAIN, default=DEFAULT_DOMAIN): cv.string,
        }
        data_schema[CONF_PORTAL_VERSION] = selector({
            "select": {
                "options": ["ginlong_v2", "soliscloud"],
            }
        })

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema), errors=errors)

    async def async_step_credentials_password(self, user_input=None):
        """Handle username/password based credential settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("User_input = %s", user_input)
            url =  self._data.get(CONF_PORTAL_DOMAIN)
            plant_id = user_input.get(CONF_PLANT_ID)
            username = user_input.get(CONF_USERNAME),
            password = user_input.get(CONF_PASSWORD),
            if url[:8] != 'https://':
                errors["base"] = "invalid_path"
            else:
                if username and password and plant_id:
                    self._data.update(user_input)
                    _LOGGER.debug("set up ginlong with user_input = %s", self._data)
                    config = GinlongConfig(url, username, password, plant_id)
                    api = GinlongAPI(config)
                    if await api.login(async_get_clientsession(self.hass)):
                        await self.async_set_unique_id(plant_id)
                        _LOGGER.debug("Unique ID set")
                        return self.async_create_entry(title=f"Station {plant_id}", data=self._data)

                    errors["base"] = "auth"

        data_schema= {
            vol.Required(CONF_USERNAME , default=None): cv.string,
            vol.Required(CONF_PASSWORD , default=''): cv.string,
            vol.Required(CONF_PLANT_ID, default=None): cv.positive_int,
        }

        return self.async_show_form(step_id="credentials_password",
            data_schema=vol.Schema(data_schema), errors=errors)

    async def async_step_credentials_secret(self, user_input=None):
        """Handle key_id/secret based credential settings."""

        if user_input is not None:
            url =  self._data.get(CONF_PORTAL_DOMAIN)
            plant_id = user_input.get(CONF_PLANT_ID)
            username = user_input.get(CONF_USERNAME)
            key_id = user_input.get(CONF_KEY_ID)
            secret: bytes = bytes(user_input.get(CONF_SECRET), 'utf-8')
            if url[:8] != 'https://':
                errors["base"] = "invalid_path"
            else:
                if username and key_id and secret and plant_id:
                    self._data.update(user_input)
                    config = SoliscloudConfig(url, username, key_id, secret, plant_id)
                    api = SoliscloudAPI(config)
                    if await api.login(async_get_clientsession(self.hass)):
                        await self.async_set_unique_id(plant_id)
                        return self.async_create_entry(title=f"Station {plant_id}", data=user_input)

                    errors["base"] = "auth"

        data_schema={
            vol.Required(CONF_USERNAME , default=None): cv.string,
            vol.Required(CONF_SECRET , default='00'): cv.string,
            vol.Required(CONF_KEY_ID , default=''): cv.string,
            vol.Required(CONF_PLANT_ID, default=None): cv.positive_int,
        }

        return self.async_show_form(step_id="credentials_secret",
            data_schema=vol.Schema(data_schema), errors=errors)

    async def async_step_import(self, user_input=None):
        """Import a config entry from configuration.yaml."""

        if user_input is not None:
            if self._async_entry_exists(user_input.get(CONF_PLANT_ID)):
                _LOGGER.debug("Already configured, aborting")
                return self.async_abort(reason="already_configured")
            url = user_input.get(CONF_PORTAL_DOMAIN)
            if url[:4] != 'http':
                # Fix URL
                url = f"https://{url}"
                user_input[CONF_PORTAL_DOMAIN] = url

            user_input[CONF_PORTAL_VERSION] = "ginlong_v2"
            has_key_id = user_input.get(CONF_KEY_ID) != ''
            has_secret: bytes = bytes(user_input.get(CONF_SECRET), 'utf-8') != b'\x00'
            if has_key_id and has_secret:
                user_input[CONF_PORTAL_VERSION] = "soliscloud"

        return await self.async_step_user(user_input)

    def _async_entry_exists(self, plant_id) -> bool:
        existing_entries = [
            int(entry.title[8:])
            for entry in self._async_current_entries()
        ]
        return plant_id in existing_entries
