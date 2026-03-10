"""Config flow for Feishu Bot integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import (
    CONF_APP_ID,
    CONF_APP_SECRET,
    DOMAIN,
)
from .exceptions import FeishuBotError
from .feishu_api import FeishuApiClient

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(user_input: dict | None = None) -> vol.Schema:
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_APP_ID, default=user_input.get(CONF_APP_ID, "")): str,
            vol.Required(CONF_APP_SECRET, default=user_input.get(CONF_APP_SECRET, "")): str,
        }
    )


class FeishuBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Feishu Bot."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors = {}

        if user_input is not None:
            data = {
                CONF_APP_ID: user_input[CONF_APP_ID].strip(),
                CONF_APP_SECRET: user_input[CONF_APP_SECRET].strip(),
            }

            try:
                await _async_validate_input(self.hass, data)
            except FeishuBotError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected validation failure")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data[CONF_APP_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Feishu Bot", data=data)

        return self.async_show_form(step_id="user", data_schema=_schema_with_defaults(user_input), errors=errors)

    async def async_step_reauth(self, entry_data: dict):
        return await self.async_step_user(entry_data)


async def _async_validate_input(hass: HomeAssistant, data: dict) -> None:
    api_client = FeishuApiClient(hass, data[CONF_APP_ID], data[CONF_APP_SECRET])
    await api_client.async_validate_connection()
