"""The Feishu Bot integration."""

from __future__ import annotations

import logging
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    ATTR_RECEIVE_ID,
    ATTR_RECEIVE_ID_TYPE,
    ATTR_TEXT,
    CONF_AGENT_ID,
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_REPLY_RECEIVE_ID_TYPE,
    DEFAULT_REPLY_RECEIVE_ID_TYPE,
    DOMAIN,
    SERVICE_SEND_TEXT,
)
from .exceptions import FeishuBotError
from .executor import HomeAssistantCommandExecutor
from .feishu_api import FeishuApiClient
from .feishu_ws_client import FeishuWsClient
from .models import RuntimeData
from .router import CommandRouter

_LOGGER = logging.getLogger(__name__)

FeishuBotConfigEntry: TypeAlias = ConfigEntry[RuntimeData]
PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_SEND_TEXT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_RECEIVE_ID): cv.string,
        vol.Required(ATTR_TEXT): cv.string,
        vol.Optional(ATTR_RECEIVE_ID_TYPE, default="chat_id"): vol.In(["chat_id", "open_id", "user_id", "union_id"]),
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FeishuBotConfigEntry) -> bool:
    app_id = entry.data[CONF_APP_ID]
    app_secret = entry.data[CONF_APP_SECRET]
    agent_id = entry.options.get(CONF_AGENT_ID, entry.data.get(CONF_AGENT_ID))
    reply_receive_id_type = entry.options.get(CONF_REPLY_RECEIVE_ID_TYPE, DEFAULT_REPLY_RECEIVE_ID_TYPE)

    api_client = FeishuApiClient(hass, app_id, app_secret)
    try:
        await api_client.async_validate_connection()
    except FeishuBotError as err:
        raise ConfigEntryNotReady(str(err)) from err

    executor = HomeAssistantCommandExecutor(hass, agent_id)
    router = CommandRouter(executor=executor, api_client=api_client, reply_receive_id_type=reply_receive_id_type)

    ws_client = FeishuWsClient(
        hass=hass,
        app_id=app_id,
        app_secret=app_secret,
        message_handler=router.async_handle_message,
    )
    await ws_client.async_start()

    entry.runtime_data = RuntimeData(ws_client=ws_client, api_client=api_client, message_handler=router.async_handle_message)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _LOGGER.info("Feishu Bot integration started")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FeishuBotConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.ws_client.async_stop()

    if len(hass.config_entries.async_entries(DOMAIN)) <= 1:
        hass.services.async_remove(DOMAIN, SERVICE_SEND_TEXT)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: FeishuBotConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    async def _handle_send_text(call: ServiceCall) -> None:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return

        runtime_data = entries[0].runtime_data
        await runtime_data.api_client.async_send_text_message(
            receive_id=call.data[ATTR_RECEIVE_ID],
            receive_id_type=call.data[ATTR_RECEIVE_ID_TYPE],
            text=call.data[ATTR_TEXT],
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_TEXT):
        hass.services.async_register(DOMAIN, SERVICE_SEND_TEXT, _handle_send_text, schema=SERVICE_SEND_TEXT_SCHEMA)
