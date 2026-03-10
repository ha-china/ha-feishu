"""Config flow for Feishu Bot integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import CONF_AGENT_ID, CONF_APP_ID, CONF_APP_SECRET, DOMAIN
from .exceptions import FeishuBotError
from .feishu_api import FeishuApiClient

_LOGGER = logging.getLogger(__name__)


def _agent_selector(hass: HomeAssistant) -> selector.ConversationAgentSelector:
    """Return HA native conversation agent selector."""
    return selector.ConversationAgentSelector({"language": hass.config.language})


async def _get_preferred_agent_id(hass: HomeAssistant) -> str:
    """Get preferred Assist pipeline conversation agent id."""
    try:
        from homeassistant.components.assist_pipeline.pipeline import async_get_pipeline

        pipeline = async_get_pipeline(hass)
        engine = getattr(pipeline, "conversation_engine", None)
        if isinstance(engine, str) and engine:
            return engine
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Unable to resolve preferred assist pipeline: %r", err)

    return ""


class FeishuBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Feishu Bot."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "FeishuBotOptionsFlowHandler":
        """Get options flow handler."""
        return FeishuBotOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        preferred_agent = await _get_preferred_agent_id(self.hass)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_APP_ID): str,
                vol.Required(CONF_APP_SECRET): str,
                vol.Optional(CONF_AGENT_ID, default=preferred_agent): _agent_selector(self.hass),
            }
        )

        if user_input is not None:
            data = {
                CONF_APP_ID: user_input[CONF_APP_ID].strip(),
                CONF_APP_SECRET: user_input[CONF_APP_SECRET].strip(),
            }
            options: dict[str, Any] = {}
            if user_input.get(CONF_AGENT_ID):
                options[CONF_AGENT_ID] = user_input[CONF_AGENT_ID]

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
                return self.async_create_entry(title="Feishu Bot", data=data, options=options)

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict):
        return await self.async_step_user(entry_data)


class FeishuBotOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Feishu Bot."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            data: dict[str, Any] = {}
            if user_input.get(CONF_AGENT_ID):
                data[CONF_AGENT_ID] = user_input[CONF_AGENT_ID]
            return self.async_create_entry(title="", data=data)

        preferred_agent = await _get_preferred_agent_id(self.hass)
        current_agent = self._config_entry.options.get(
            CONF_AGENT_ID,
            self._config_entry.data.get(CONF_AGENT_ID, preferred_agent),
        )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_AGENT_ID, default=current_agent): _agent_selector(self.hass),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


async def _async_validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    api_client = FeishuApiClient(hass, data[CONF_APP_ID], data[CONF_APP_SECRET])
    await api_client.async_validate_connection()
