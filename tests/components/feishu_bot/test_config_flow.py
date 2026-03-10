"""Tests for Feishu Bot config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow

from custom_components.feishu_bot.const import DOMAIN


async def test_form(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass):
    with patch("custom_components.feishu_bot.config_flow._async_validate_input", new=AsyncMock(return_value=None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "app_id": "cli_xxx",
                "app_secret": "secret",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Feishu Bot"
