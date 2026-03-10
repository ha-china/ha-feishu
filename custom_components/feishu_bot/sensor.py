"""Status sensor for Feishu Bot integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up status sensor for one config entry."""
    async_add_entities([FeishuBotStatusSensor(entry)])


class FeishuBotStatusSensor(SensorEntity):
    """Expose websocket connection state as a diagnostic sensor."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:websocket"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_translation_key = "status"
        self._attr_native_value = "disconnected"
        self._unsub = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Feishu Bot",
            "manufacturer": "Feishu",
            "model": "WebSocket Bot",
        }

    async def async_added_to_hass(self) -> None:
        ws_client = self._entry.runtime_data.ws_client

        def _handle_status(status: str) -> None:
            self._attr_native_value = status
            self.async_write_ha_state()

        self._unsub = ws_client.register_status_listener(_handle_status)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
